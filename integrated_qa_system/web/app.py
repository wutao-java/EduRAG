import logging
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .dependencies import lifespan
from .routers import chat_router, health_router, sessions_router, system_router

logger = logging.getLogger(__name__)

router = APIRouter()
router.include_router(health_router)
router.include_router(system_router)
router.include_router(sessions_router)
router.include_router(chat_router)


async def handle_unhandled_exception(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    logger.error(
        "未处理的 HTTP 异常，method=%s，path=%s",
        request.method,
        request.url.path,
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"},
    )


def create_app(qa_system: Any = None) -> FastAPI:
    application = FastAPI(
        title="问答系统API",
        description="集成MySQL、RAG和Agent的智能问答系统",
        lifespan=lifespan,
    )
    application.state.qa_system = qa_system
    application.state.owns_qa_system = False

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_exception_handler(Exception, handle_unhandled_exception)
    application.include_router(router)
    return application


app = create_app()
