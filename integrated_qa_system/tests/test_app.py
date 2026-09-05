import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

from integrated_qa_system.app import create_app
from integrated_qa_system.application import ChatDecision, check_greeting


class FakeBM25Search:
    def __init__(self):
        self.calls = []

    def search(self, query, threshold):
        self.calls.append((query, threshold))
        if query == "需要 Agent":
            return None, True
        return "FAQ 答案", False


class FakeQASystem:
    def __init__(self):
        self.config = SimpleNamespace(VALID_SOURCES=["java", "ai"])
        self.bm25_search = FakeBM25Search()
        self.history = []

    def update_session_history(self, session_id, question, answer):
        self.history.append((session_id, question, answer))

    def prepare_query(self, query):
        greeting = check_greeting(query)
        if greeting:
            return ChatDecision(answer=greeting, requires_agent=False)
        answer, needs_agent = self.bm25_search.search(query, 0.85)
        return ChatDecision(
            answer=answer or (None if needs_agent else "未找到答案"),
            requires_agent=needs_agent,
        )

    def query_faq_suggestions(self):
        return ["什么是 RAG？"]

    def query(self, query, source_filter=None, session_id=None):
        decision = self.prepare_query(query)
        if decision.requires_agent:
            answer = "Agent 答案"
            self.update_session_history(session_id, query, answer)
            yield answer, False
            yield "", True
            return
        self.update_session_history(session_id, query, decision.answer)
        yield decision.answer, True


class AppTest(unittest.TestCase):
    def setUp(self):
        self.qa_system = FakeQASystem()
        self.client = self.enterContext(TestClient(create_app(self.qa_system)))

    def test_service_metadata_and_health(self):
        self.assertEqual(
            {
                "name": "EduRAG API",
                "docs": "/docs",
                "health": "/health",
            },
            self.client.get("/").json(),
        )
        self.assertEqual(
            {"status": "healthy"},
            self.client.get("/health").json(),
        )

    def test_greeting_skips_bm25_and_records_history(self):
        response = self.client.post(
            "/api/query",
            json={"query": " 你好 ", "session_id": "session-1"},
        )

        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()["is_streaming"])
        self.assertEqual([], self.qa_system.bm25_search.calls)
        self.assertEqual("session-1", self.qa_system.history[0][0])

    def test_rejects_unknown_source(self):
        response = self.client.post(
            "/api/query",
            json={"query": "Java 是什么？", "source_filter": "unknown"},
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual("无效的学科类别: unknown", response.json()["detail"])

    def test_returns_faq_suggestions(self):
        response = self.client.get("/api/faq/suggestions")

        self.assertEqual(200, response.status_code)
        self.assertEqual(["什么是 RAG？"], response.json()["suggestions"])

    def test_agent_query_switches_to_websocket(self):
        response = self.client.post(
            "/api/query",
            json={"query": "需要 Agent", "session_id": "session-1"},
        )

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["is_streaming"])
        self.assertEqual([], self.qa_system.history)

    def test_websocket_keeps_stream_contract_and_saves_once(self):
        with self.client.websocket_connect("/api/stream") as websocket:
            websocket.send_json(
                {"query": "需要 Agent", "session_id": "session-1"}
            )
            self.assertEqual("start", websocket.receive_json()["type"])
            token_message = websocket.receive_json()
            self.assertEqual(
                {"type": "token", "token": "Agent 答案", "session_id": "session-1"},
                token_message,
            )
            self.assertEqual("end", websocket.receive_json()["type"])

        self.assertEqual(
            [("session-1", "需要 Agent", "Agent 答案")],
            self.qa_system.history,
        )


if __name__ == "__main__":
    unittest.main()
