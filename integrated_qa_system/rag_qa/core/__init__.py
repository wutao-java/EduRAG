# -*- coding: utf-8 -*-
__all__ = ["QueryClassifier", "RAGSystem", "VectorStore"]


def __getattr__(name):
    """避免导入轻量服务时立即初始化深度学习依赖。"""

    if name == "QueryClassifier":
        from .query_classifier import QueryClassifier

        return QueryClassifier
    if name == "RAGSystem":
        from .rag_system import RAGSystem

        return RAGSystem
    if name == "VectorStore":
        from .vector_store import VectorStore

        return VectorStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
