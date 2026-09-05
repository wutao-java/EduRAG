import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ..dependencies import get_qa_system
from ..schemas import SessionTitleRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["sessions"])


async def _create_session(qa_system, title):
    session_id = str(uuid.uuid4())
    return await run_in_threadpool(
        qa_system.create_session,
        session_id,
        title,
    )


@router.post("/create_session")
async def create_session(request: Request):
    qa_system = get_qa_system(request)
    return await _create_session(qa_system, "新的学习问题")


@router.post("/sessions")
async def create_named_session(
    request_data: SessionTitleRequest,
    request: Request,
):
    qa_system = get_qa_system(request)
    return await _create_session(qa_system, request_data.title)


@router.get("/sessions")
async def list_sessions(request: Request):
    qa_system = get_qa_system(request)
    sessions = await run_in_threadpool(qa_system.list_sessions)
    return {"sessions": sessions}


@router.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    request_data: SessionTitleRequest,
    request: Request,
):
    qa_system = get_qa_system(request)
    try:
        success = await run_in_threadpool(
            qa_system.rename_session,
            session_id,
            request_data.title,
        )
    except Exception as exception:
        logger.exception("更新会话标题失败，session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="更新会话标题失败") from exception
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"session_id": session_id, "title": request_data.title}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    qa_system = get_qa_system(request)
    success = await run_in_threadpool(qa_system.delete_session, session_id)
    if not success:
        raise HTTPException(status_code=500, detail="删除会话失败")
    return {"status": "success", "message": "会话已删除"}


@router.get("/history/{session_id}")
async def get_history(session_id: str, request: Request):
    qa_system = get_qa_system(request)
    try:
        history = await run_in_threadpool(
            qa_system.get_session_history,
            session_id,
        )
        return {"session_id": session_id, "history": history}
    except Exception as exception:
        logger.exception("获取历史记录失败，session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="获取历史记录失败") from exception


@router.delete("/history/{session_id}")
async def clear_history(session_id: str, request: Request):
    qa_system = get_qa_system(request)
    success = await run_in_threadpool(
        qa_system.clear_session_history,
        session_id,
    )
    if not success:
        raise HTTPException(status_code=500, detail="清除历史记录失败")
    return {"status": "success", "message": "历史记录已清除"}
