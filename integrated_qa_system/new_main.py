# 导入 MySQL 和 Redis 客户端，管理数据库和缓存
from mysql_qa import MySQLClient, RedisClient, BM25Search
from mysql_qa.core import FAQSuggestionService
# 导入 RAG 系统组件，用于知识库检索和答案生成
from rag_qa import VectorStore, RAGSystem
# 导入配置和日志工具，用于系统配置和日志记录
from base import logger, Config
# 导入 OpenAI 客户端，用于调用 DashScope API
from openai import OpenAI
# 导入时间库，用于记录处理时间
import time
# 导入 UUID 库，生成唯一会话 ID
import uuid
# 导入 pymysql 错误处理，用于数据库操作的异常捕获
import pymysql


class IntegratedQASystem:
    def __init__(self):
        # 初始化日志工具，用于记录系统运行信息
        self.logger = logger
        # 初始化配置对象，加载系统参数
        self.config = Config()
        # 初始化 MySQL 客户端，用于数据库操作
        self.mysql_client = MySQLClient()
        # 初始化 Redis 客户端，用于缓存管理
        self.redis_client = RedisClient()
        self.faq_suggestion_service = FAQSuggestionService(
            self.redis_client,
            self.mysql_client,
        )
        # 初始化 BM25 搜索模块，结合 MySQL 和 Redis
        self.bm25_search = BM25Search(self.redis_client, self.mysql_client)
        try:
            # 初始化 OpenAI 客户端，连接 DashScope API
            self.client = OpenAI(api_key=self.config.DASHSCOPE_API_KEY,
                                 base_url=self.config.DASHSCOPE_BASE_URL)
        except Exception as e:
            # 记录 OpenAI 初始化失败的错误日志
            self.logger.error(f"OpenAI 客户端初始化失败: {e}")
            # 抛出异常，终止初始化
            raise
        # 初始化向量存储，用于 RAG 系统的知识库管理
        self.vector_store = VectorStore()
        # 初始化 RAG 系统，传入向量存储和 DashScope API 调用函数
        self.rag_system = RAGSystem(
            self.vector_store,
            self.call_dashscope,
            self.stream_dashscope,
        )
        # 初始化对话历史表，用于存储会话记录
        self.init_conversation_table()

    def call_dashscope(self, prompt):
        """调用DashScope API生成答案（流式输出）"""
        return "".join(self.stream_dashscope(prompt))

    def stream_dashscope(self, prompt):
        """调用DashScope API并逐块返回模型输出"""
        try:
            completions = self.client.chat.completions.create(
                model=self.config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个有用的助手"},
                    {"role": "user", "content": prompt},
                ],
                timeout=30,
                stream=True
            )

            for chunk in completions:
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None)
                if content:
                    yield content

        except Exception as e:
            self.logger.error(f"调用DashScope API失败 {e}")
            yield f"错误：LLM调用失败 - {e}"

    def init_conversation_table(self):
        """初始化MySQL中的会话和对话历史表"""
        try:
            with self.mysql_client.cursor_context(commit=True) as cursor:
                # 创建 conversations 表，包含会话 ID、问题、答案和时间戳
                cursor.execute("""
                               CREATE TABLE IF NOT EXISTS conversations (
                                   id INT AUTO_INCREMENT PRIMARY KEY,
                                   session_id VARCHAR(36) NOT NULL,
                                   question TEXT NOT NULL,
                                   answer TEXT NOT NULL,
                                   timestamp DATETIME NOT NULL,
                                   INDEX idx_session_id (session_id)
                               );
                               """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_sessions (
                        session_id VARCHAR(36) PRIMARY KEY,
                        title VARCHAR(80) NOT NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_updated_at (updated_at)
                    );
                """)
            # 记录表初始化成功的日志
            # self.logger.info("对话历史表初始化成功")
        except pymysql.MySQLError as e:
            # 记录表初始化失败的错误日志
            self.logger.error(f"初始化对话历史表失败: {e}")
            # 抛出异常，终止初始化
            raise

    def create_session(self, session_id: str, title: str) -> dict:
        """创建会话元数据"""
        try:
            normalized_title = title.strip()[:80] or "新的学习问题"
            with self.mysql_client.cursor_context(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO conversation_sessions (session_id, title)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE title = VALUES(title), updated_at = NOW()
                """, (session_id, normalized_title))
                cursor.execute("""
                    SELECT updated_at
                    FROM conversation_sessions
                    WHERE session_id = %s
                """, (session_id,))
                updated_at = cursor.fetchone()[0]
            return {
                "session_id": session_id,
                "title": normalized_title,
                "updated_at": updated_at.isoformat(timespec="seconds"),
            }
        except pymysql.MySQLError:
            raise

    def list_sessions(self) -> list:
        """获取最近使用的会话列表"""
        with self.mysql_client.cursor_context() as cursor:
            cursor.execute("""
                SELECT session_id, title, updated_at
                FROM conversation_sessions
                ORDER BY updated_at DESC
                LIMIT 20
            """)
            return [
                {
                    "session_id": row[0],
                    "title": row[1],
                    "updated_at": row[2].isoformat(timespec="seconds"),
                }
                for row in cursor.fetchall()
            ]

    def rename_session(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        try:
            with self.mysql_client.cursor_context(commit=True) as cursor:
                cursor.execute("""
                    UPDATE conversation_sessions
                    SET title = %s, updated_at = NOW()
                    WHERE session_id = %s
                """, (title.strip()[:80], session_id))
                return cursor.rowcount > 0
        except pymysql.MySQLError:
            raise

    def delete_session(self, session_id: str) -> bool:
        """删除会话及其历史记录"""
        try:
            with self.mysql_client.cursor_context(commit=True) as cursor:
                cursor.execute(
                    "DELETE FROM conversations WHERE session_id = %s",
                    (session_id,),
                )
                cursor.execute(
                    "DELETE FROM conversation_sessions WHERE session_id = %s",
                    (session_id,),
                )
            return True
        except pymysql.MySQLError:
            return False

    def _touch_session(self, cursor, session_id: str, title: str) -> None:
        """确保会话存在并刷新最近访问时间"""
        normalized_title = title.strip()[:80] or "新的学习问题"
        cursor.execute("""
            INSERT INTO conversation_sessions (session_id, title)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE updated_at = NOW()
        """, (session_id, normalized_title))

    @staticmethod
    def _read_recent_history(cursor, session_id: str) -> list:
        cursor.execute("""
            SELECT question, answer
            FROM conversations
            WHERE session_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """, (session_id, 5))
        history = [{"question": row[0], "answer": row[1]} for row in cursor.fetchall()]
        return history[::-1]

    def _fetch_recent_history(self, session_id: str) -> list:
        """获取最近5轮对话历史"""
        try:
            with self.mysql_client.cursor_context() as cursor:
                return self._read_recent_history(cursor, session_id)
        except pymysql.MySQLError as e:
            # 记录查询失败的错误日志
            self.logger.error(f"获取对话历史失败: {e}")
            # 返回空列表
            return []

    def update_session_history(self, session_id: str, question: str, answer: str) -> list:
        """更新会话历史到MySQL，保留最近5轮对话"""
        try:
            with self.mysql_client.cursor_context(commit=True) as cursor:
                self._touch_session(cursor, session_id, question)
                # 插入新的对话记录
                cursor.execute("""
                    INSERT INTO conversations (session_id, question, answer, timestamp)
                    VALUES (%s, %s, %s, NOW())
                """, (session_id, question, answer))
                # 获取更新后的对话历史
                history = self._read_recent_history(cursor, session_id)
                # 删除超出 5 轮的旧记录
                cursor.execute("""
                    DELETE FROM conversations
                    WHERE session_id = %s AND id NOT IN (
                        SELECT id FROM (
                            SELECT id
                            FROM conversations
                            WHERE session_id = %s
                            ORDER BY timestamp DESC
                            LIMIT %s
                        ) AS sub
                    )
                """, (session_id, session_id, 5))
            # 记录更新成功的日志
            self.logger.info(f"会话 {session_id} 历史更新成功")
            # 返回更新后的历史
            return history
        except pymysql.MySQLError as e:
            # 记录数据库操作失败的错误日志
            self.logger.error(f"更新会话历史失败: {e}")
            # 抛出异常
            raise
        except Exception as e:
            # 记录意外错误的日志
            self.logger.error(f"更新会话历史意外错误: {e}")
            # 抛出异常
            raise

    def clear_session_history(self, session_id: str) -> bool:
        """清除指定会话历史"""
        try:
            with self.mysql_client.cursor_context(commit=True) as cursor:
                # 删除指定 session_id 的所有对话记录
                cursor.execute("""
                    DELETE FROM conversations
                    WHERE session_id = %s
                """, (session_id,))
            # 记录清除成功的日志
            self.logger.info(f"会话 {session_id} 历史已清除")
            # 返回 True 表示成功
            return True
        except pymysql.MySQLError as e:
            # 记录清除失败的错误日志
            self.logger.error(f"清除会话历史失败: {e}")
            # 返回 False 表示失败
            return False

    def get_session_history(self, session_id: str) -> list:
        """从MySQL获取会话历史"""
        # 调用 _fetch_recent_history 获取对话历史
        return self._fetch_recent_history(session_id)

    def query_faq_suggestions(self) -> list:
        """查询前端“试着问”问题。"""

        return self.faq_suggestion_service.query()

    def query(self, query, source_filter=None, session_id=None):
        """查询集成系统，支持对话历史和流式输出"""
        start_time = time.time()  # 记录查询开始时间
        # 记录查询信息到日志
        self.logger.info(f"处理查询: '{query}' (会话ID: {session_id})")
        # 获取对话历史，若无 session_id 则返回空列表
        history = self.get_session_history(session_id) if session_id else []
        # 执行 BM25 搜索，获取答案和是否需要 RAG 的标志
        answer, need_rag = self.bm25_search.search(query, threshold=0.85)
        if answer:
            # 如果找到可靠答案，记录答案到日志
            self.logger.info(f"MySQL答案: {answer}")
            if session_id:
                # 更新对话历史
                self.update_session_history(session_id, query, answer)
            # 计算处理时间
            processing_time = time.time() - start_time
            # 记录处理时间到日志
            self.logger.info(f"查询处理耗时 {processing_time:.2f}秒")
            # 一次性返回答案，标记为完整
            yield answer, True
        elif need_rag:
            # 如果需要 RAG，记录回退信息到日志
            self.logger.info("无可靠MySQL答案，回退到RAG")
            # 初始化收集完整答案的字符串
            collected_answer = ""
            # 从 RAG 系统获取流式输出
            for token in self.rag_system.stream_answer(query, source_filter=source_filter, history=history):
                # 累积答案
                collected_answer += token
                # 逐 token 返回，标记为部分答案
                yield token, False
            if session_id:
                # 更新对话历史，存储完整答案
                self.update_session_history(session_id, query, collected_answer)
            # 计算处理时间
            processing_time = time.time() - start_time
            # 记录处理时间到日志
            self.logger.info(f"查询处理耗时 {processing_time:.2f}秒")
            # 返回空字符串，标记流结束
            yield "", True
        else:
            # 如果无答案，记录信息到日志
            self.logger.info("未找到答案")
            # 计算处理时间
            processing_time = time.time() - start_time
            # 记录处理时间到日志
            self.logger.info(f"查询处理耗时 {processing_time:.2f}秒")
            # 一次性返回默认答案，标记为完整
            yield "未找到答案", True

def main():
    # 定义主函数，提供命令行交互界面
    qa_system = IntegratedQASystem()  # 初始化问答系统
    # 生成唯一会话 ID
    session_id = str(uuid.uuid4())
    # 打印欢迎信息
    print("\n欢迎使用集成问答系统！")
    # 打印会话 ID
    print(f"会话ID: {session_id}")
    # 打印支持的学科类别
    print(f"支持的学科类别：{qa_system.config.VALID_SOURCES}")
    # 提示用户输入查询或退出
    print("输入查询进行问答，输入 'exit' 退出。")
    try:
        while True:
            # 获取用户输入的查询
            query = input("\n输入查询: ").strip()
            if query.lower() == "exit":
                # 如果用户输入 exit，记录退出日志
                logger.info("退出系统")
                # 打印退出信息
                print("再见！")
                # 退出循环
                break
            # 获取用户输入的学科过滤
            source_filter = input(f"请输入学科类别 ({'/'.join(qa_system.config.VALID_SOURCES)}) (直接回车默认不过滤): ").strip()
            if source_filter and source_filter not in qa_system.config.VALID_SOURCES:
                # 如果学科过滤无效，记录警告日志
                logger.warning(f"无效的学科类别 '{source_filter}'，将不过滤")
                # 设置为空，忽略过滤
                source_filter = None
            # 打印答案提示
            print("\n答案: ", end="", flush=True)
            # 初始化累积答案的字符串
            answer = ""
            # 迭代 query 方法的生成器
            for token, is_complete in qa_system.query(query, source_filter=source_filter, session_id=session_id):
                if token:
                    # 仅当 token 非空时打印
                    print(token, end="", flush=True)
                    # 累积答案
                    answer += token
                if is_complete:
                    # 如果是完整答案或流结束，换行并退出循环
                    print()
                    break
            # 打印对话历史
            history = qa_system.get_session_history(session_id)
            print("\n最近对话历史:")
            for idx, entry in enumerate(history, 1):
                # 按顺序打印历史记录
                print(f"{idx}. 问: {entry['question']}\n   答: {entry['answer']}")
    except Exception as e:
        # 记录系统错误日志
        logger.error(f"系统错误: {e}")
        # 打印错误信息
        print(f"发生错误: {e}")
    finally:
        # 关闭 MySQL 连接
        qa_system.mysql_client.close()

if __name__ == "__main__":
    # 如果脚本作为主程序运行，调用 main 函数
    main()
