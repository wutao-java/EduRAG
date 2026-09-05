import logging

from .prompts import RAGPrompts

logger = logging.getLogger(__name__)


class RAGAnswerGenerator:
    """根据检索证据和对话历史生成最终回答。"""

    def __init__(self, stream_llm, customer_service_phone):
        self.stream_llm = stream_llm
        self.customer_service_phone = customer_service_phone
        self.prompt = RAGPrompts.rag_prompt()

    def generate_answer(self, query, documents, history=None, category=None):
        return "".join(
            self.stream_answer(
                query,
                documents,
                history=history,
                category=category,
            )
        )

    def stream_answer(self, query, documents, history=None, category=None):
        prompt = self._build_prompt(query, documents, history)
        try:
            response = self.stream_llm(prompt)
            if isinstance(response, str):
                if response:
                    yield response
                return
            for chunk in response:
                if chunk:
                    yield chunk
        except Exception:
            logger.exception("生成回答失败，category=%s", category)
            if category == "通用知识":
                yield (
                    "抱歉，处理您的通用知识问题时出错。"
                    f"请联系人工客服：{self.customer_service_phone}"
                )
            else:
                yield (
                    "抱歉，处理您的专业咨询问题时出错。"
                    f"请联系人工客服：{self.customer_service_phone}"
                )

    def _build_prompt(self, query, documents, history):
        context = "\n\n".join(
            getattr(document, "page_content", str(document))
            for document in documents
        )
        history_text = "\n\n".join(
            f"第{index}轮\n用户：{item['question']}\n助手：{item['answer']}"
            for index, item in enumerate(history or [], start=1)
        ) or "无"
        return self.prompt.format(
            context=context,
            history=history_text,
            question=query,
            phone=self.customer_service_phone,
        )
