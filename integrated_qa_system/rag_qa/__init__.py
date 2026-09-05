# -*- coding: utf-8 -*-
__all__ = ["RAGSystem", "VectorStore"]


def __getattr__(name):
    """仅在实际使用时加载本地大模型和 Milvus 依赖。"""

    if name == "RAGSystem":
        from .core.rag_system import RAGSystem

        return RAGSystem
    if name == "VectorStore":
        from .core.vector_store import VectorStore

        return VectorStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
