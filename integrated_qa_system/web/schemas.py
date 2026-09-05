from pydantic import BaseModel, field_validator


class QueryRequest(BaseModel):
    """HTTP 非流式查询的请求数据。"""

    query: str
    source_filter: str | None = None
    session_id: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("查询内容不能为空")
        return normalized_value

    @field_validator("source_filter", "session_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None


class QueryResponse(BaseModel):
    """HTTP 查询接口返回给前端的统一数据结构。"""

    answer: str
    is_streaming: bool
    session_id: str
    processing_time: float


class FAQSuggestionResponse(BaseModel):
    """“试着问”接口返回数据。"""

    suggestions: list[str]


class SessionTitleRequest(BaseModel):
    """会话创建和重命名请求。"""

    title: str = "新的学习问题"

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("会话标题不能为空")
        return normalized_value[:80]
