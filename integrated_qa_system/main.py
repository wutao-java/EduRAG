import time
import uuid

try:
    from .base import logger
    from .bootstrap import build_container
except ImportError:
    from base import logger
    from bootstrap import build_container


class IntegratedQASystem:
    """保留旧接口的兼容门面，业务实现由独立服务负责。"""

    def __init__(self, container=None):
        self.container = container or build_container()
        self.logger = logger
        self.config = self.container.config
        self.mysql_client = self.container.mysql_client
        self.redis_client = self.container.redis_client
        self.client = self.container.llm_client.client
        self.faq_suggestion_service = self.container.faq_suggestion_service
        self.bm25_search = self.container.faq_search
        self.vector_store = self.container.vector_store
        self.rag_system = self.container.rag_system
        self.agent = self.container.agent
        self.conversation_service = self.container.conversation_service
        self.chat_service = self.container.chat_service

    def call_dashscope(self, prompt):
        return self.container.llm_client.complete(prompt)

    def stream_dashscope(self, prompt):
        yield from self.container.llm_client.stream(prompt)

    def init_conversation_table(self):
        self.conversation_service.initialize()

    def create_session(self, session_id, title):
        return self.conversation_service.create_session(session_id, title)

    def list_sessions(self):
        return self.conversation_service.list_sessions()

    def rename_session(self, session_id, title):
        return self.conversation_service.rename_session(session_id, title)

    def delete_session(self, session_id):
        return self.conversation_service.delete_session(session_id)

    def update_session_history(self, session_id, question, answer):
        return self.conversation_service.append_history(
            session_id,
            question,
            answer,
        )

    def clear_session_history(self, session_id):
        return self.conversation_service.clear_history(session_id)

    def get_session_history(self, session_id):
        return self.conversation_service.get_history(session_id)

    def query_faq_suggestions(self):
        return self.faq_suggestion_service.query()

    def prepare_query(self, query):
        return self.chat_service.prepare(query)

    def query(self, query, source_filter=None, session_id=None):
        start_time = time.perf_counter()
        yield from self.chat_service.stream(
            query,
            source_filter=source_filter,
            session_id=session_id,
        )
        self.logger.info(
            "查询处理完成，session_id=%s，耗时=%.2fs",
            session_id,
            time.perf_counter() - start_time,
        )

    def close(self):
        self.container.close()


def main():
    qa_system = IntegratedQASystem()
    session_id = str(uuid.uuid4())
    print("\n欢迎使用集成问答系统！")
    print(f"会话ID: {session_id}")
    print(f"支持的学科类别：{qa_system.config.VALID_SOURCES}")
    print("输入查询进行问答，输入 'exit' 退出。")

    try:
        while True:
            query = input("\n输入查询: ").strip()
            if query.lower() == "exit":
                print("再见！")
                break

            source_filter = input(
                f"请输入学科类别 ({'/'.join(qa_system.config.VALID_SOURCES)}) "
                "(直接回车默认不过滤): "
            ).strip()
            if source_filter and source_filter not in qa_system.config.VALID_SOURCES:
                logger.warning("无效的学科类别 '%s'，将不过滤", source_filter)
                source_filter = None

            print("\n答案: ", end="", flush=True)
            for token, is_complete in qa_system.query(
                query,
                source_filter=source_filter,
                session_id=session_id,
            ):
                if token:
                    print(token, end="", flush=True)
                if is_complete:
                    print()
                    break

            print("\n最近对话历史:")
            for index, entry in enumerate(
                qa_system.get_session_history(session_id),
                start=1,
            ):
                print(
                    f"{index}. 问: {entry['question']}\n"
                    f"   答: {entry['answer']}"
                )
    except Exception as exception:  # noqa: BLE001 - CLI 边界需要转换为用户可读错误。
        logger.exception("系统错误")
        print(f"发生错误: {exception}")
    finally:
        qa_system.close()


if __name__ == "__main__":
    main()
