import logging
from dataclasses import dataclass

from .prompts import RAGPrompts

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievalPlan:
    category: str
    strategy: str | None

    @property
    def requires_knowledge(self):
        return self.category == "专业咨询"


@dataclass(frozen=True)
class RetrievalResult:
    plan: RetrievalPlan
    documents: list


class RetrievalService:
    """负责查询规划和知识检索，不负责生成最终回答。"""

    def __init__(
        self,
        vector_store,
        llm,
        query_classifier,
        strategy_selector,
        retrieval_k,
        candidate_m,
    ):
        self.vector_store = vector_store
        self.llm = llm
        self.query_classifier = query_classifier
        self.strategy_selector = strategy_selector
        self.retrieval_k = retrieval_k
        self.candidate_m = candidate_m

    def plan(self, query):
        category = self.query_classifier.predict_category(query)
        strategy = None
        if category == "专业咨询":
            strategy = self.strategy_selector.select_strategy(query)
        return RetrievalPlan(category=category, strategy=strategy)

    def retrieve(self, query, source_filter=None):
        plan = self.plan(query)
        documents = []
        if plan.requires_knowledge:
            documents = self.search(
                query,
                source_filter=source_filter,
                strategy=plan.strategy,
            )
        return RetrievalResult(plan=plan, documents=documents)

    def search(self, query, source_filter=None, strategy=None):
        if strategy == "回溯问题检索":
            documents = self._search_with_backtracking(query, source_filter)
        elif strategy == "子查询检索":
            documents = self._search_with_subqueries(query, source_filter)
        elif strategy == "假设问题检索":
            documents = self._search_with_hyde(query, source_filter)
        else:
            documents = self._search(query, source_filter)
        return documents[:self.candidate_m]

    def _search(self, query, source_filter):
        return self.vector_store.hybrid_search_with_rerank(
            query,
            k=self.retrieval_k,
            source_filter=source_filter,
        )

    def _search_with_hyde(self, query, source_filter):
        prompt = RAGPrompts.hyde_prompt().format(query=query)
        try:
            hypothetical_answer = self.llm(prompt).strip()
            return self._search(hypothetical_answer, source_filter)
        except Exception:
            logger.exception("HyDE 检索失败")
            return []

    def _search_with_subqueries(self, query, source_filter):
        prompt = RAGPrompts.subquery_prompt().format(query=query)
        try:
            response = self.llm(prompt).strip()
            subqueries = [line.strip() for line in response.splitlines() if line.strip()]
            documents = []
            for subquery in subqueries:
                documents.extend(self._search(subquery, source_filter))
            return list({self._document_key(doc): doc for doc in documents}.values())
        except Exception:
            logger.exception("子查询检索失败")
            return []

    def _search_with_backtracking(self, query, source_filter):
        prompt = RAGPrompts.backtracking_prompt().format(query=query)
        try:
            simplified_query = self.llm(prompt).strip()
            return self._search(simplified_query, source_filter)
        except Exception:
            logger.exception("回溯问题检索失败")
            return []

    @staticmethod
    def _document_key(document):
        return getattr(document, "page_content", str(document))
