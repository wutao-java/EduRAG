import unittest

from integrated_qa_system.agent.graph import EducationAgent
from integrated_qa_system.rag_qa.core.retrieval_service import (
    RetrievalPlan,
)


class FakeRetrievalService:
    def __init__(self, requires_knowledge):
        self.requires_knowledge = requires_knowledge
        self.search_calls = []

    def plan(self, query):
        return RetrievalPlan(
            category="专业咨询" if self.requires_knowledge else "通用知识",
            strategy="直接检索" if self.requires_knowledge else None,
        )

    def search(self, query, source_filter=None, strategy=None):
        self.search_calls.append((query, source_filter, strategy))
        return ["knowledge"]


class FakeAnswerGenerator:
    def __init__(self):
        self.calls = []

    def stream_answer(self, query, documents, history=None, category=None):
        self.calls.append((query, documents, history, category))
        yield "流式"
        yield "答案"


class EducationAgentTest(unittest.TestCase):
    def test_professional_query_calls_knowledge_tool_and_streams_answer(self):
        retrieval_service = FakeRetrievalService(requires_knowledge=True)
        answer_generator = FakeAnswerGenerator()
        agent = EducationAgent(retrieval_service, answer_generator)

        tokens = list(
            agent.stream(
                "Java 课程大纲",
                source_filter="java",
                history=[{"question": "上一问", "answer": "上一答"}],
            )
        )

        self.assertEqual(["流式", "答案"], tokens)
        self.assertEqual(
            [("Java 课程大纲", "java", "直接检索")],
            retrieval_service.search_calls,
        )
        self.assertEqual(["knowledge"], answer_generator.calls[0][1])

    def test_general_query_skips_knowledge_tool(self):
        retrieval_service = FakeRetrievalService(requires_knowledge=False)
        answer_generator = FakeAnswerGenerator()
        agent = EducationAgent(retrieval_service, answer_generator)

        answer = agent.invoke("1+1 等于多少")

        self.assertEqual("流式答案", answer)
        self.assertEqual([], retrieval_service.search_calls)
        self.assertEqual([], answer_generator.calls[0][1])


if __name__ == "__main__":
    unittest.main()
