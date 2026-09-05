from dataclasses import dataclass
from typing import Any


@dataclass
class ServiceContainer:
    config: Any
    mysql_client: Any
    redis_client: Any
    llm_client: Any
    faq_search: Any
    faq_suggestion_service: Any
    conversation_service: Any
    vector_store: Any
    rag_system: Any
    agent: Any
    chat_service: Any

    def close(self):
        self.mysql_client.close()

        redis_connection = getattr(self.redis_client, "client", None)
        close_redis = getattr(redis_connection, "close", None)
        if callable(close_redis):
            close_redis()

        self.llm_client.close()


def build_container():
    """集中创建应用依赖；模块导入阶段不连接外部服务。"""

    if __package__:
        from .agent import EducationAgent
        from .application import ChatService
        from .base import Config
        from .conversation import ConversationService, MySQLConversationRepository
        from .infrastructure.llm import DashScopeClient
        from .mysql_qa import BM25Search, MySQLClient, RedisClient
        from .mysql_qa.core import FAQSuggestionService
        from .rag_qa import RAGSystem, VectorStore
        from .rag_qa.core.strategy_selector import StrategySelector
    else:
        from agent import EducationAgent
        from application import ChatService
        from base import Config
        from conversation import ConversationService, MySQLConversationRepository
        from infrastructure.llm import DashScopeClient
        from mysql_qa import BM25Search, MySQLClient, RedisClient
        from mysql_qa.core import FAQSuggestionService
        from rag_qa import RAGSystem, VectorStore
        from rag_qa.core.strategy_selector import StrategySelector

    config = Config()
    mysql_client = MySQLClient()
    redis_client = RedisClient()
    conversation_service = ConversationService(
        MySQLConversationRepository(mysql_client)
    )
    conversation_service.initialize()

    llm_client = DashScopeClient(
        api_key=config.DASHSCOPE_API_KEY,
        base_url=config.DASHSCOPE_BASE_URL,
        model=config.LLM_MODEL,
    )
    faq_search = BM25Search(redis_client, mysql_client)
    faq_suggestion_service = FAQSuggestionService(redis_client, mysql_client)
    vector_store = VectorStore()
    strategy_selector = StrategySelector(
        llm=lambda prompt: llm_client.complete(prompt, temperature=0)
    )
    rag_system = RAGSystem(
        vector_store,
        llm_client.complete,
        llm_client.stream,
        strategy_selector=strategy_selector,
        config=config,
    )
    agent = EducationAgent(
        rag_system.retrieval_service,
        rag_system.answer_generator,
    )
    chat_service = ChatService(
        faq_search,
        agent,
        conversation_service,
    )
    return ServiceContainer(
        config=config,
        mysql_client=mysql_client,
        redis_client=redis_client,
        llm_client=llm_client,
        faq_search=faq_search,
        faq_suggestion_service=faq_suggestion_service,
        conversation_service=conversation_service,
        vector_store=vector_store,
        rag_system=rag_system,
        agent=agent,
        chat_service=chat_service,
    )
