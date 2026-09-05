import unittest

from integrated_qa_system.application.chat_service import ChatService


class FakeFAQSearch:
    def __init__(self, answer=None, needs_agent=True):
        self.answer = answer
        self.needs_agent = needs_agent
        self.calls = []

    def search(self, query, threshold):
        self.calls.append((query, threshold))
        return self.answer, self.needs_agent


class FakeAgent:
    def __init__(self):
        self.calls = []

    def stream(self, query, source_filter=None, history=None):
        self.calls.append((query, source_filter, history))
        yield "Agent"
        yield "答案"


class FakeConversationService:
    def __init__(self):
        self.history = [{"question": "上一问", "answer": "上一答"}]
        self.saved = []

    def get_history(self, session_id):
        return self.history

    def append_history(self, session_id, question, answer):
        self.saved.append((session_id, question, answer))


class ChatServiceTest(unittest.TestCase):
    def test_high_confidence_faq_skips_agent_and_saves_once(self):
        faq_search = FakeFAQSearch(answer="FAQ 答案", needs_agent=False)
        agent = FakeAgent()
        conversations = FakeConversationService()
        service = ChatService(faq_search, agent, conversations)

        chunks = list(service.stream("Java 是什么", session_id="session-1"))

        self.assertEqual([("FAQ 答案", True)], chunks)
        self.assertEqual([], agent.calls)
        self.assertEqual(
            [("session-1", "Java 是什么", "FAQ 答案")],
            conversations.saved,
        )

    def test_agent_answer_is_streamed_and_saved_once(self):
        faq_search = FakeFAQSearch()
        agent = FakeAgent()
        conversations = FakeConversationService()
        service = ChatService(faq_search, agent, conversations)

        chunks = list(
            service.stream(
                "Java 课程大纲",
                source_filter="java",
                session_id="session-1",
            )
        )

        self.assertEqual(
            [("Agent", False), ("答案", False), ("", True)],
            chunks,
        )
        self.assertEqual(
            [("Java 课程大纲", "java", conversations.history)],
            agent.calls,
        )
        self.assertEqual(
            [("session-1", "Java 课程大纲", "Agent答案")],
            conversations.saved,
        )


if __name__ == "__main__":
    unittest.main()
