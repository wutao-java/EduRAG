import re
from dataclasses import dataclass

GREETING_PATTERNS = (
    (
        r"^(你好|您好|hi|hello)",
        "你好！我是涛小将，专注于为学生答疑解惑，很高兴为你服务！",
    ),
    (
        r"^(你是谁|您是谁|你叫什么|你的名字|who are you)",
        "我是涛小将，你的智能学习助手，致力于提供 IT 教育相关的解答！",
    ),
    (r"^(在吗|在不在|有人吗)", "我在！我是涛小将，随时为你解答问题！"),
    (
        r"^(干嘛呢|你在干嘛|做什么)",
        "我正在待命，随时为你解答 IT 学习相关的问题！有什么我可以帮你的？",
    ),
)


def check_greeting(query):
    query_text = query.strip()
    for pattern, response in GREETING_PATTERNS:
        if re.match(pattern, query_text, re.IGNORECASE):
            return response
    return None


@dataclass(frozen=True)
class ChatDecision:
    answer: str | None
    requires_agent: bool


class ChatService:
    FAQ_THRESHOLD = 0.85

    def __init__(self, faq_search, agent, conversation_service):
        self.faq_search = faq_search
        self.agent = agent
        self.conversation_service = conversation_service

    def prepare(self, query):
        greeting = check_greeting(query)
        if greeting:
            return ChatDecision(answer=greeting, requires_agent=False)

        answer, needs_agent = self.faq_search.search(
            query,
            threshold=self.FAQ_THRESHOLD,
        )
        if needs_agent:
            return ChatDecision(answer=None, requires_agent=True)
        return ChatDecision(answer=answer or "未找到答案", requires_agent=False)

    def stream(self, query, source_filter=None, session_id=None):
        decision = self.prepare(query)
        if not decision.requires_agent:
            if session_id:
                self.conversation_service.append_history(
                    session_id,
                    query,
                    decision.answer,
                )
            yield decision.answer, True
            return

        history = (
            self.conversation_service.get_history(session_id)
            if session_id
            else []
        )
        answer_chunks = []
        for token in self.agent.stream(
            query,
            source_filter=source_filter,
            history=history,
        ):
            answer_chunks.append(token)
            yield token, False

        if session_id:
            self.conversation_service.append_history(
                session_id,
                query,
                "".join(answer_chunks),
            )
        yield "", True
