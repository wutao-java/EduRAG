import unittest

from integrated_qa_system.conversation.service import ConversationService


class FakeConversationRepository:
    def __init__(self):
        self.initialized = False
        self.created = None
        self.renamed = None
        self.appended = None

    def initialize(self):
        self.initialized = True

    def create_session(self, session_id, title):
        self.created = (session_id, title)
        return {"session_id": session_id, "title": title}

    def rename_session(self, session_id, title):
        self.renamed = (session_id, title)
        return True

    def append_history(self, session_id, question, answer, limit):
        self.appended = (session_id, question, answer, limit)
        return [{"question": question, "answer": answer}]


class ConversationServiceTest(unittest.TestCase):
    def setUp(self):
        self.repository = FakeConversationRepository()
        self.service = ConversationService(self.repository, history_limit=5)

    def test_normalizes_session_title(self):
        result = self.service.create_session("session-1", "  Java 学习  ")

        self.assertEqual(("session-1", "Java 学习"), self.repository.created)
        self.assertEqual("Java 学习", result["title"])

    def test_uses_default_title_and_limits_length(self):
        self.service.create_session("session-1", "   ")
        self.assertEqual(("session-1", "新的学习问题"), self.repository.created)

        self.service.rename_session("session-1", "x" * 100)
        self.assertEqual(("session-1", "x" * 80), self.repository.renamed)

    def test_appends_history_with_configured_limit(self):
        result = self.service.append_history("session-1", "问题", "答案")

        self.assertEqual(
            ("session-1", "问题", "答案", 5),
            self.repository.appended,
        )
        self.assertEqual([{"question": "问题", "answer": "答案"}], result)


if __name__ == "__main__":
    unittest.main()
