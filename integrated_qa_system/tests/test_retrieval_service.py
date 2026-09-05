import unittest

from integrated_qa_system.rag_qa.core.retrieval_service import RetrievalService


class FakeClassifier:
    def __init__(self, category):
        self.category = category

    def predict_category(self, query):
        return self.category


class FakeStrategySelector:
    def __init__(self):
        self.queries = []

    def select_strategy(self, query):
        self.queries.append(query)
        return "直接检索"


class FakeVectorStore:
    def __init__(self):
        self.calls = []

    def hybrid_search_with_rerank(self, query, k, source_filter=None):
        self.calls.append((query, k, source_filter))
        return ["document"]


class RetrievalServiceTest(unittest.TestCase):
    def test_general_query_skips_strategy_and_knowledge_search(self):
        selector = FakeStrategySelector()
        vector_store = FakeVectorStore()
        service = RetrievalService(
            vector_store=vector_store,
            llm=lambda prompt: "",
            query_classifier=FakeClassifier("通用知识"),
            strategy_selector=selector,
            retrieval_k=8,
            candidate_m=3,
        )

        result = service.retrieve("1+1 等于多少")

        self.assertFalse(result.plan.requires_knowledge)
        self.assertEqual([], result.documents)
        self.assertEqual([], selector.queries)
        self.assertEqual([], vector_store.calls)

    def test_professional_query_uses_planned_strategy_and_source_filter(self):
        selector = FakeStrategySelector()
        vector_store = FakeVectorStore()
        service = RetrievalService(
            vector_store=vector_store,
            llm=lambda prompt: "",
            query_classifier=FakeClassifier("专业咨询"),
            strategy_selector=selector,
            retrieval_k=8,
            candidate_m=3,
        )

        result = service.retrieve("Java 课程大纲", source_filter="java")

        self.assertTrue(result.plan.requires_knowledge)
        self.assertEqual("直接检索", result.plan.strategy)
        self.assertEqual(["Java 课程大纲"], selector.queries)
        self.assertEqual([("Java 课程大纲", 8, "java")], vector_store.calls)
        self.assertEqual(["document"], result.documents)


if __name__ == "__main__":
    unittest.main()
