from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from .state import AgentState
from .tools import KnowledgeSearchTool


class EducationAgent:
    """使用 LangGraph 编排查询规划、知识检索和答案生成。"""

    def __init__(self, retrieval_service, answer_generator):
        self.retrieval_service = retrieval_service
        self.answer_generator = answer_generator
        self.knowledge_search = KnowledgeSearchTool(retrieval_service)
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("plan", self._plan)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("answer", self._answer)
        graph.add_edge(START, "plan")
        graph.add_conditional_edges(
            "plan",
            self._route_after_plan,
            {"retrieve": "retrieve", "answer": "answer"},
        )
        graph.add_edge("retrieve", "answer")
        graph.add_edge("answer", END)
        return graph.compile()

    def _plan(self, state):
        return {"plan": self.retrieval_service.plan(state["query"])}

    @staticmethod
    def _route_after_plan(state):
        return "retrieve" if state["plan"].requires_knowledge else "answer"

    def _retrieve(self, state):
        return {
            "documents": self.knowledge_search.invoke(
                state["query"],
                source_filter=state.get("source_filter"),
                strategy=state["plan"].strategy,
            )
        }

    def _answer(self, state):
        writer = get_stream_writer()
        chunks = []
        for token in self.answer_generator.stream_answer(
            state["query"],
            state.get("documents", []),
            history=state.get("history", []),
            category=state["plan"].category,
        ):
            chunks.append(token)
            writer({"type": "token", "token": token})
        return {"answer": "".join(chunks)}

    def stream(self, query, source_filter=None, history=None):
        state = {
            "query": query,
            "source_filter": source_filter,
            "history": history or [],
            "documents": [],
        }
        for mode, event in self.graph.stream(
            state,
            stream_mode=["custom", "values"],
        ):
            if mode == "custom" and event.get("type") == "token":
                yield event["token"]

    def invoke(self, query, source_filter=None, history=None):
        state = self.graph.invoke(
            {
                "query": query,
                "source_filter": source_filter,
                "history": history or [],
                "documents": [],
            }
        )
        return state["answer"]
