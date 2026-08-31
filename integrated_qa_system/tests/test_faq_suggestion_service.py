# -*- coding: utf-8 -*-
import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "mysql_qa" / "core.py"
MODULE_SPEC = importlib.util.spec_from_file_location(
    "faq_suggestion_service",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)
FAQSuggestionService = MODULE.FAQSuggestionService


class FakeRedisClient:
    def __init__(self, cached_value=None):
        self.cached_value = cached_value
        self.saved_value = None

    def get_data(self, key):
        return self.cached_value

    def set_data(self, key, value, expire_seconds=None):
        self.saved_value = (key, value, expire_seconds)


class FakeMySQLClient:
    def __init__(self, pairs):
        self.pairs = pairs
        self.requested_limit = None

    def fetch_faq_pairs(self, limit):
        self.requested_limit = limit
        return self.pairs


class FAQSuggestionServiceTest(unittest.TestCase):
    def test_returns_cached_suggestions_without_querying_mysql(self):
        redis_client = FakeRedisClient([" Java 基础 ", "Java 基础"])
        mysql_client = FakeMySQLClient([])

        suggestions = FAQSuggestionService(redis_client, mysql_client).query()

        self.assertEqual(["Java 基础"], suggestions)
        self.assertIsNone(mysql_client.requested_limit)

    def test_queries_mysql_and_caches_normalized_questions(self):
        redis_client = FakeRedisClient()
        mysql_client = FakeMySQLClient(
            [
                {"question": " 什么是 RAG？", "answer": "..."},
                {"question": "什么是 RAG？", "answer": "..."},
                {"question": "如何学习 Java？", "answer": "..."},
            ]
        )

        suggestions = FAQSuggestionService(
            redis_client,
            mysql_client,
            limit=10,
        ).query()

        self.assertEqual(["什么是 RAG？", "如何学习 Java？"], suggestions)
        self.assertEqual(10, mysql_client.requested_limit)
        self.assertEqual(
            (
                FAQSuggestionService.CACHE_KEY,
                suggestions,
                FAQSuggestionService.CACHE_TTL_SECONDS,
            ),
            redis_client.saved_value,
        )


if __name__ == "__main__":
    unittest.main()
