class KnowledgeSearchTool:
    name = "knowledge_search"
    description = "检索教育知识库并返回与问题相关的证据。"

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    def invoke(self, query, source_filter=None, strategy=None):
        return self.retrieval_service.search(
            query,
            source_filter=source_filter,
            strategy=strategy,
        )
