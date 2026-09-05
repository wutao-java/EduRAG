import unittest
from types import SimpleNamespace

from integrated_qa_system.rag_qa.core.rag_system import RAGSystem
from integrated_qa_system.rag_qa.core.retrieval_service import (
    RetrievalPlan,
    RetrievalResult,
)


class FakeRetrievalService:
    query_classifier = object()
    strategy_selector = object()

    def __init__(self):
        self.retrieve_calls = []
        self.search_calls = []

    def retrieve(self, query, source_filter=None):
        self.retrieve_calls.append((query, source_filter))
        return RetrievalResult(
            plan=RetrievalPlan("专业咨询", "直接检索"),
            documents=["证据"],
        )

    def search(self, query, source_filter=None, strategy=None):
        self.search_calls.append((query, source_filter, strategy))
        return ["证据"]


class FakeAnswerGenerator:
    def __init__(self):
        self.calls = []

    def stream_answer(self, query, documents, history=None, category=None):
        self.calls.append((query, documents, history, category))
        yield "兼容答案"


class RAGSystemTest(unittest.TestCase):
    def setUp(self):
        self.retrieval_service = FakeRetrievalService()
        self.answer_generator = FakeAnswerGenerator()
        self.rag_system = RAGSystem(
            vector_store=object(),
            llm=lambda prompt: "",
            retrieval_service=self.retrieval_service,
            answer_generator=self.answer_generator,
            config=SimpleNamespace(CUSTOMER_SERVICE_PHONE="123"),
        )

    def test_stream_answer_delegates_to_retrieval_and_answer_services(self):
        answer = self.rag_system.generate_answer(
            "Java 课程大纲",
            source_filter="java",
            history=[{"question": "上一问", "answer": "上一答"}],
        )

        self.assertEqual("兼容答案", answer)
        self.assertEqual(
            [("Java 课程大纲", "java")],
            self.retrieval_service.retrieve_calls,
        )
        self.assertEqual("专业咨询", self.answer_generator.calls[0][3])

    def test_retrieve_and_merge_keeps_public_compatibility_method(self):
        documents = self.rag_system.retrieve_and_merge(
            "Java 课程大纲",
            source_filter="java",
            strategy="直接检索",
        )

        self.assertEqual(["证据"], documents)
        self.assertEqual(
            [("Java 课程大纲", "java", "直接检索")],
            self.retrieval_service.search_calls,
        )


if __name__ == "__main__":
    unittest.main()
