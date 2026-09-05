# -*-coding:utf-8-*-
# 导入正则表达式模块，用于识别查询中的比较连接词
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 导入 LangChain 的提示词模板类，用于将用户查询填充到策略选择提示词中
from langchain_core.prompts import PromptTemplate
# 导入项目日志对象和配置读取类
from base import logger, Config
# 导入 OpenAI 客户端，调用 DashScope 提供的 OpenAI 兼容接口
from openai import OpenAI


# 定义检索策略选择器，负责通过本地规则或大模型选择检索策略
class StrategySelector:
    # 定义系统允许返回的全部策略名称，用于校验大模型输出
    VALID_STRATEGIES = ("直接检索", "假设问题检索", "子查询检索", "回溯问题检索")
    # 定义比较意图关键词；查询包含这些词时，可能需要拆分为多个子查询
    COMPARISON_KEYWORDS = ("区别", "差异", "比较", "对比", "优缺点", "哪个好", "哪个更")
    # 编译比较对象连接词正则，用于识别“Java 和 Python”“Milvus vs Zilliz”等表达
    COMPARISON_CONNECTOR_PATTERN = re.compile(r"(?:和|与|跟|及|以及|、|vs\.?|versus)", re.IGNORECASE)
    # 定义明确事实查询模式，用于识别学费、课程大纲、报名条件等单一信息查询
    DIRECT_QUERY_PATTERNS = (
        # 匹配费用、学费和价格等数值型事实查询
        re.compile(r"(?:学费|费用|价格).*(?:多少|几|是什么)", re.IGNORECASE),
        # 匹配课程安排、报名条件、时间、地址、联系方式和教师等明确事实查询
        re.compile(r"(?:课程大纲|课程安排|报名条件|开课时间|上课时间|地址|联系方式|授课老师|教师).*(?:是什么|有哪些|谁|多少|在哪里)?", re.IGNORECASE),
    )
    # 定义抽象开放查询模式，用于识别适合先生成假设答案再检索的问题
    HYDE_QUERY_PATTERNS = (
        # 匹配应用、价值、意义、影响、趋势和前景等开放性主题查询
        re.compile(r"(?:应用|价值|意义|作用|影响|趋势|前景|发展).*(?:有哪些|是什么|如何|怎样)", re.IGNORECASE),
        # 匹配要求理解抽象概念、原理、价值或意义的查询
        re.compile(r"(?:如何|怎么|怎样)理解.+(?:概念|原理|价值|意义)?", re.IGNORECASE),
    )
    # 定义复杂场景关键词，用于判断查询是否包含具体业务背景或实施要求
    BACKTRACK_SCENARIO_PATTERN = re.compile(r"(?:我有|如果|假设|现有|需要|想要|计划|场景|情况下)", re.IGNORECASE)
    # 定义可行性关键词，用于判断查询是否要求评估能力边界或设计实施方案
    BACKTRACK_FEASIBILITY_PATTERN = re.compile(
        r"(?:能不能|是否可行|可以吗|可不可以|是否支持|能否支持|如何实现|怎么实现|如何设计|怎么设计|如何规划|怎么规划)",
        re.IGNORECASE,
    )
    # 定义规模和性能约束，用于识别需要先回溯基础能力再回答的复杂查询
    BACKTRACK_CONSTRAINT_PATTERN = re.compile(
        r"(?:\d+\s*(?:万|亿|w|k|m|g|tb|gb|条|个|并发|毫秒|秒)|大规模|海量|高并发|低延迟)",
        re.IGNORECASE,
    )

    # 初始化策略选择器及其依赖对象
    def __init__(self, llm=None):
        self.llm = llm
        self.client = None
        if llm is None:
            # 兼容独立运行方式；应用运行时由组合根注入共享 LLM 客户端。
            self.client = OpenAI(
                api_key=Config().DASHSCOPE_API_KEY,
                base_url=Config().DASHSCOPE_BASE_URL,
            )
        # 创建并保存策略选择提示词模板，供后续查询重复使用
        self.strategy_prompt_template = self._get_strategy_prompt()

    # 调用 DashScope 大模型，并返回模型生成的策略名称
    def call_dashscope(self, prompt):
        if self.llm is not None:
            return self.llm(prompt)

        # 捕获网络、鉴权、模型配置和响应解析等调用异常
        try:
            # 通过 OpenAI 兼容接口创建一次聊天补全请求
            completion = self.client.chat.completions.create(
                # 从配置文件读取需要调用的大模型名称
                model=Config().LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个有用的助手。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0
            )
            # 检查响应是否包含候选结果以及候选消息内容
            if not completion.choices or not completion.choices[0].message.content:
                # 当接口返回空结果时抛出异常，避免将空内容当作有效策略
                raise RuntimeError("DashScope API 未返回策略")
            # 返回第一条候选消息中的策略文本
            return completion.choices[0].message.content
        # 捕获本次 DashScope 调用过程中产生的所有异常
        except Exception as e:
            # 将调用失败原因写入项目日志，方便定位接口或配置问题
            logger.error(f"DashScope API 调用失败: {e}")
            # 包装并继续抛出异常，避免把接口失败错误地伪装成某个检索策略
            raise RuntimeError(f"DashScope API 调用失败: {e}") from e

    # 创建用于指导大模型选择检索策略的提示词模板
    def _get_strategy_prompt(self):
        # 返回一个包含四种检索策略说明、示例和输出约束的提示词模板
        return PromptTemplate(
            # 定义提示词正文；其中的 query 占位符会在调用前替换为用户查询
            template="""
            你是一个智能助手，负责分析用户查询 {query}，并从以下四种检索增强策略中选择一个最适合的策略，直接返回策略名称，不需要解释过程。

            以下是几种检索增强策略及其适用场景：

            1.  **直接检索：**
                * 描述：对用户查询直接进行检索，不进行任何增强处理。
                * 适用场景：适用于查询意图明确，需要从知识库中检索**特定信息**的问题，例如：
                    * 示例：
                        * 查询：AI 学科学费是多少？
                        * 策略：直接检索
                    * 查询：JAVA的课程大纲是什么？
                        * 策略：直接检索
            2.  **假设问题检索（HyDE）：**
                * 描述：使用 LLM 生成一个假设的答案，然后基于假设答案进行检索。
                * 适用场景：适用于查询较为抽象，直接检索效果不佳的问题，例如：
                    * 示例：
                        * 查询：人工智能在教育领域的应用有哪些？
                        * 策略：假设问题检索
            3.  **子查询检索：**
                * 描述：将复杂的用户查询拆分为多个简单的子查询，分别检索并合并结果。
                * 适用场景：适用于查询涉及多个实体或方面，需要分别检索不同信息的问题，例如：
                    * 示例：
                        * 查询：比较 Milvus 和 Zilliz Cloud 的优缺点。
                        * 策略：子查询检索
                        * 查询：Java 和 Python 有什么区别？
                        * 策略：子查询检索
            4.  **回溯问题检索：**
                * 描述：将复杂的用户查询转化为更基础、更易于检索的问题，然后进行检索。
                * 适用场景：适用于查询较为复杂，需要简化后才能有效检索的问题，例如：
                    * 示例：
                        * 查询：我有一个包含 100 亿条记录的数据集，想把它存储到 Milvus 中进行查询。可以吗？
                        * 策略：回溯问题检索
                        * 查询：Mysql 数据库能不能支持 100w 个样本的插入？
                        * 策略：回溯问题检索

            请按照以下优先级进行判定：
            1. 查询要求比较多个对象，或者需要分别回答多个独立方面时，选择“子查询检索”。
            2. 查询包含具体场景、数据规模、性能约束，并要求判断可行性或设计方案时，选择“回溯问题检索”。
            3. 查询主题宽泛抽象，要求说明应用、价值、影响、趋势或前景时，选择“假设问题检索”。
            4. 查询只要求一个明确事实、数值、人员、时间、地址或课程信息时，选择“直接检索”。

            根据用户查询 {query}，只能返回“直接检索”“假设问题检索”“子查询检索”“回溯问题检索”中的一个名称，不要输出任何分析过程或其他内容。
            """
            ,
            # 声明提示词模板需要接收的变量名称
            input_variables=["query"],
        )

    # 根据用户查询选择并返回最终检索策略
    def select_strategy(self, query):
        # 优先使用高置信度本地规则选择策略，无法确定时再调用大模型
        strategy = self._select_by_rule(query)
        # 判断本地规则是否已经得到明确策略
        if strategy:
            # 记录本地规则选择出的策略及其对应查询
            logger.info(f"为查询 '{query}' 选择的检索策略：{strategy}")
            # 直接返回本地规则结果，避免不必要的大模型调用
            return strategy
        # 将用户查询填充到提示词模板中，调用大模型选择其他类型的检索策略
        raw_strategy = self.call_dashscope(self.strategy_prompt_template.format(query=query))
        # 从模型响应中提取并校验唯一合法的策略名称
        strategy = self._normalize_strategy(raw_strategy)
        # 记录大模型选择出的策略及其对应查询
        logger.info(f"为查询 '{query}' 选择的检索策略：{strategy}")
        # 返回去除首尾空白字符后的策略名称
        return strategy

    # 按照策略优先级执行高置信度本地规则匹配
    @classmethod
    # 返回匹配到的策略名称；没有高置信度结果时返回空值并交给大模型判断
    def _select_by_rule(cls, query):
        # 去除查询首尾空白字符，统一后续规则的输入
        normalized_query = query.strip()
        # 比较多个对象的查询优先拆分为多个子查询
        if cls._is_comparison_query(normalized_query):
            # 返回子查询检索策略
            return "子查询检索"
        # 带场景或规模约束的可行性问题需要先回溯基础能力
        if cls._is_backtrack_query(normalized_query):
            # 返回回溯问题检索策略
            return "回溯问题检索"
        # 抽象、开放的主题问题适合使用假设答案增强检索
        if cls._matches_patterns(normalized_query, cls.HYDE_QUERY_PATTERNS):
            # 返回假设问题检索策略
            return "假设问题检索"
        # 单一且明确的事实查询可以直接检索
        if cls._matches_patterns(normalized_query, cls.DIRECT_QUERY_PATTERNS):
            # 返回直接检索策略
            return "直接检索"
        # 无法高置信度判断时返回空值，避免本地规则过度匹配
        return None

    # 声明类方法，用于复用一组正则表达式判断查询
    @classmethod
    # 判断查询是否匹配给定模式集合中的任意一个模式
    def _matches_patterns(cls, query, patterns):
        # 逐个执行正则搜索，只要一个模式匹配就返回真
        return any(pattern.search(query) for pattern in patterns)

    # 声明类方法，用于判断复杂场景可行性问题
    @classmethod
    # 判断查询是否同时包含可行性意图以及场景或规模约束
    def _is_backtrack_query(cls, query):
        # 判断查询是否要求评估可行性或设计实现方案
        has_feasibility_intent = bool(cls.BACKTRACK_FEASIBILITY_PATTERN.search(query))
        # 判断查询是否包含具体业务场景描述
        has_scenario = bool(cls.BACKTRACK_SCENARIO_PATTERN.search(query))
        # 判断查询是否包含数据规模、性能或容量约束
        has_constraint = bool(cls.BACKTRACK_CONSTRAINT_PATTERN.search(query))
        # 仅在可行性意图与至少一种复杂约束同时存在时判为回溯问题
        return has_feasibility_intent and (has_scenario or has_constraint)

    # 声明类方法，用于规范化并校验大模型返回的策略文本
    @classmethod
    # 从模型响应中提取唯一合法策略，拒绝无法识别或存在歧义的响应
    def _normalize_strategy(cls, raw_strategy):
        # 查找模型响应中出现的全部合法策略名称
        matched_strategies = [strategy for strategy in cls.VALID_STRATEGIES if strategy in raw_strategy]
        # 只有恰好匹配一个合法策略时才接受模型结果
        if len(matched_strategies) == 1:
            # 返回唯一匹配到的规范策略名称
            return matched_strategies[0]
        # 抛出异常，阻止非法或含多个策略的模型输出继续进入检索流程
        raise ValueError(f"无效的检索策略: {raw_strategy}")

    # 声明类方法，使比较规则可以直接访问类级关键词和正则表达式
    @classmethod
    # 判断用户查询是否同时包含比较意图词和比较对象连接词
    def _is_comparison_query(cls, query):
        # 去除查询首尾空白字符，避免空格影响关键词匹配
        normalized_query = query.strip()
        # 判断查询中是否至少包含一个预定义的比较意图关键词
        has_comparison_intent = any(keyword in normalized_query for keyword in cls.COMPARISON_KEYWORDS)
        # 仅当比较意图和对象连接词同时存在时，才将查询识别为比较类查询
        return has_comparison_intent and bool(cls.COMPARISON_CONNECTOR_PATTERN.search(normalized_query))


# 仅在直接运行当前模块时执行下面的策略选择示例
if __name__ == '__main__':
    # 创建策略选择器实例
    ss = StrategySelector()
    print(ss.select_strategy('Mysql数据库能不能支持100w个样本的插入'))
