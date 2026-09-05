import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


def create_qa_system():
    """延迟创建问答系统，避免模块导入时加载模型和外部连接。"""

    from ..application.system import IntegratedQASystem

    return IntegratedQASystem()


def close_qa_system(qa_system: Any) -> None:
    """释放问答系统持有的外部资源。"""

    close_system = getattr(qa_system, "close", None)
    if callable(close_system):
        close_system()
        return

    mysql_client = getattr(qa_system, "mysql_client", None)
    if mysql_client is not None:
        mysql_client.close()

    redis_client = getattr(qa_system, "redis_client", None)
    redis_connection = getattr(redis_client, "client", None)
    close_redis = getattr(redis_connection, "close", None)
    if callable(close_redis):
        close_redis()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """在应用生命周期内初始化并释放问答系统。"""

    if app.state.qa_system is None:
        app.state.qa_system = await run_in_threadpool(create_qa_system)
        app.state.owns_qa_system = True

    try:
        yield
    finally:
        if app.state.owns_qa_system and app.state.qa_system is not None:
            await run_in_threadpool(close_qa_system, app.state.qa_system)


def get_qa_system(request: Request):
    qa_system = request.app.state.qa_system
    if qa_system is None:
        raise HTTPException(status_code=503, detail="问答系统尚未就绪")
    return qa_system


def validate_source_filter(
    source_filter: str | None,
    qa_system: Any,
) -> None:
    valid_sources = qa_system.config.VALID_SOURCES
    if source_filter and source_filter not in valid_sources:
        raise ValueError(f"无效的学科类别: {source_filter}")


async def record_history(
    qa_system: Any,
    session_id: str,
    question: str,
    answer: str,
) -> None:
    try:
        await run_in_threadpool(
            qa_system.update_session_history,
            session_id,
            question,
            answer,
        )
    except Exception:
        logger.exception("会话历史写入失败，session_id=%s", session_id)
