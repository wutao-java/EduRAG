import logging

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(self, repository, history_limit=5):
        self.repository = repository
        self.history_limit = history_limit

    def initialize(self):
        self.repository.initialize()

    def create_session(self, session_id, title):
        return self.repository.create_session(
            session_id,
            self._normalize_title(title),
        )

    def list_sessions(self):
        return self.repository.list_sessions()

    def rename_session(self, session_id, title):
        return self.repository.rename_session(
            session_id,
            self._normalize_title(title),
        )

    def delete_session(self, session_id):
        try:
            return self.repository.delete_session(session_id)
        except Exception:
            logger.exception("删除会话失败，session_id=%s", session_id)
            return False

    def get_history(self, session_id):
        try:
            return self.repository.get_history(session_id, self.history_limit)
        except Exception:
            logger.exception("获取会话历史失败，session_id=%s", session_id)
            return []

    def append_history(self, session_id, question, answer):
        return self.repository.append_history(
            session_id,
            question,
            answer,
            self.history_limit,
        )

    def clear_history(self, session_id):
        try:
            return self.repository.clear_history(session_id)
        except Exception:
            logger.exception("清除会话历史失败，session_id=%s", session_id)
            return False

    @staticmethod
    def _normalize_title(title):
        return title.strip()[:80] or "新的学习问题"
