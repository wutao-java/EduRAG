# -*-coding:utf-8-*-
# retrieval/bm25_search.py
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 导入 BM25 算法
from rank_bm25 import BM25Okapi
# 导入文本预处理
from mysql_qa.utils.preprocess import preprocess_text
# 导入日志
from base import logger
from mysql_qa.cache.redis_client import RedisClient
from mysql_qa.db.mysql_client import MySQLClient


class BM25Search:
    def __init__(self, redis_client, mysql_client):
        # 初始化日志
        # 初始化 BM25 模型
        self.bm25 = None
        # 初始化分词问题列表
        self.questions = None
        # 初始化原始问题列表
        self.original_questions = None
        # 加载数据
        self.redis_client=redis_client
        self.mysql_client = mysql_client
        self.logger = logger
        self._load_data()

    def _load_data(self):
        # 加载数据
        original_key = "qa_original_questions"
        tokenized_key = "qa_tokenized_questions"
        question_rows = self.mysql_client.fetch_questions()
        if not question_rows:
            question_rows = self.redis_client.get_data(original_key)
        if not question_rows:
            self.logger.warning("未加载到问题")
            return
        self.original_questions = [
            question[0] if isinstance(question, (list, tuple)) else question
            for question in question_rows
        ]
        tokenized_questions = [
            preprocess_text(question) for question in self.original_questions
        ]
        self.redis_client.set_data(original_key, self.original_questions)
        self.redis_client.set_data(tokenized_key, tokenized_questions)
        # 设置问题列表
        self.questions = tokenized_questions
        # 初始化 BM25 模型
        self.bm25 = BM25Okapi(self.questions)
        # 记录 BM25 初始化成功
        self.logger.info("BM25 模型初始化完成")

    def search(self, query, threshold=0.85):
        # 搜索查询
        if not query or not isinstance(query, str):
            # 记录无效查询
            self.logger.error("无效查询")
            # 返回 None 和 False
            return None, False
        # 检查 Redis 缓存
        cached_answer = self.redis_client.get_answer(query)
        if cached_answer:
            # 返回缓存答案
            return cached_answer, False
        try:
            # 分词查询
            query_tokens = preprocess_text(query)
            if not query_tokens or self.bm25 is None:
                return None, True
            # 计算 BM25 分数
            scores = self.bm25.get_scores(query_tokens)
            # 获取最高分索引
            best_idx = scores.argmax()
            query_terms = set(query_tokens)
            question_terms = set(self.questions[best_idx])
            overlap_count = len(query_terms & question_terms)
            relevance_score = (
                2 * overlap_count / (len(query_terms) + len(question_terms))
            )
            # 检查是否超过阈值
            if overlap_count > 0 and relevance_score >= threshold:
                # 获取原始问题
                original_question = self.original_questions[best_idx]
                # 获取答案
                answer = self.mysql_client.fetch_answer(original_question)
                if answer:
                    # 缓存答案
                    self.redis_client.set_answer(query, answer)
                    # 记录搜索成功
                    self.logger.info(f"搜索成功，词项相似度: {relevance_score:.3f}")
                    # 返回答案和 False
                    return answer, False
            # 记录无可靠答案
            self.logger.info(f"未找到可靠答案，最高词项相似度: {relevance_score:.3f}")
            # 返回 None 和 True
            return None, True
        except Exception as e:
            # 记录搜索失败
            self.logger.error(f"搜索失败: {e}")
            # 返回 None 和 True
            return None, True


if __name__ == '__main__':
    redis_client = RedisClient()
    mysql_client = MySQLClient()
    bm25 = BM25Search(redis_client, mysql_client)
    print(bm25.search('用上下文管理器实现函数运行时间的计算'))
