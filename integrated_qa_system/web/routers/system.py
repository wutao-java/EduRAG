import logging

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ..dependencies import get_qa_system
from ..schemas import FAQSuggestionResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", include_in_schema=False)
async def read_root():
    return {
        "name": "EduRAG API",
        "docs": "/docs",
        "health": "/health",
    }


@router.get("/api/sources")
async def get_sources(request: Request):
    qa_system = get_qa_system(request)
    return {"sources": qa_system.config.VALID_SOURCES}


@router.get(
    "/api/faq/suggestions",
    response_model=FAQSuggestionResponse,
)
async def get_faq_suggestions(request: Request):
    qa_system = get_qa_system(request)
    try:
        suggestions = await run_in_threadpool(qa_system.query_faq_suggestions)
        return {"suggestions": suggestions}
    except Exception as exception:
        logger.exception("获取 FAQ 推荐问题失败")
        raise HTTPException(
            status_code=500,
            detail="获取推荐问题失败",
        ) from exception
