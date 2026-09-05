import logging

try:
    from ...base import Config
except ImportError:
    from base import Config

from .answer_generator import RAGAnswerGenerator
from .retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class RAGSystem:
    """兼容原有调用方式的 RAG 门面。"""

    def __init__(
        self,
        vector_store,
        llm,
        stream_llm=None,
        retrieval_service=None,
        answer_generator=None,
        query_classifier=None,
        strategy_selector=None,
        config=None,
    ):
        self.vector_store = vector_store
        self.llm = llm
        self.stream_llm = stream_llm or self._stream_complete_response
        self.config = config or Config()

        if retrieval_service is None:
            from .query_classifier import QueryClassifier
            from .strategy_selector import StrategySelector

            query_classifier = query_classifier or QueryClassifier()
            strategy_selector = strategy_selector or StrategySelector(llm=llm)
            retrieval_service = RetrievalService(
                vector_store=vector_store,
                llm=llm,
                query_classifier=query_classifier,
                strategy_selector=strategy_selector,
                retrieval_k=self.config.RETRIEVAL_K,
                candidate_m=self.config.CANDIDATE_M,
            )

        self.retrieval_service = retrieval_service
        self.query_classifier = retrieval_service.query_classifier
        self.strategy_selector = retrieval_service.strategy_selector
        self.answer_generator = answer_generator or RAGAnswerGenerator(
            self.stream_llm,
            self.config.CUSTOMER_SERVICE_PHONE,
        )

    def _stream_complete_response(self, prompt):
        answer = self.llm(prompt)
        if answer:
            yield answer

    def retrieve_and_merge(self, query, source_filter=None, strategy=None):
        return self.retrieval_service.search(
            query,
            source_filter=source_filter,
            strategy=strategy,
        )

    def generate_answer(self, query, source_filter=None, history=None):
        return "".join(
            self.stream_answer(
                query,
                source_filter=source_filter,
                history=history,
            )
        )

    def stream_answer(self, query, source_filter=None, history=None):
        result = self.retrieval_service.retrieve(
            query,
            source_filter=source_filter,
        )
        logger.info(
            "RAG 查询规划完成，category=%s, strategy=%s, documents=%s",
            result.plan.category,
            result.plan.strategy,
            len(result.documents),
        )
        yield from self.answer_generator.stream_answer(
            query,
            result.documents,
            history=history,
            category=result.plan.category,
        )


if __name__ == "__main__":
    from .strategy_selector import StrategySelector
    from .vector_store import VectorStore

    vector_store = VectorStore()
    strategy_selector = StrategySelector()
    rag_system = RAGSystem(vector_store, strategy_selector.call_dashscope)
    print(rag_system.generate_answer("AI学科学费是多少？"))
