from typing import Any, TypedDict

try:
    from ..rag_qa.core.retrieval_service import RetrievalPlan
except ImportError:
    from rag_qa.core.retrieval_service import RetrievalPlan


class AgentState(TypedDict, total=False):
    query: str
    source_filter: str | None
    history: list[dict[str, str]]
    plan: RetrievalPlan
    documents: list[Any]
    answer: str
