import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, WebSocket
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool
from starlette.websockets import WebSocketDisconnect, WebSocketState

from ..dependencies import get_qa_system, record_history, validate_source_filter
from ..schemas import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/query", response_model=QueryResponse)
async def query(request_data: QueryRequest, request: Request):
    start_time = time.perf_counter()
    qa_system = get_qa_system(request)
    session_id = request_data.session_id or str(uuid.uuid4())

    try:
        validate_source_filter(request_data.source_filter, qa_system)
    except ValueError as exception:
        raise HTTPException(status_code=400, detail=str(exception)) from exception

    decision = await run_in_threadpool(
        qa_system.prepare_query,
        request_data.query,
    )
    if decision.requires_agent:
        return {
            "answer": "请使用WebSocket接口获取流式响应",
            "is_streaming": True,
            "session_id": session_id,
            "processing_time": time.perf_counter() - start_time,
        }

    await record_history(
        qa_system,
        session_id,
        request_data.query,
        decision.answer,
    )
    return {
        "answer": decision.answer,
        "is_streaming": False,
        "session_id": session_id,
        "processing_time": time.perf_counter() - start_time,
    }


async def send_websocket_error(
    websocket: WebSocket,
    error_message: str,
    session_id: str | None = None,
) -> None:
    if websocket.client_state != WebSocketState.CONNECTED:
        return

    message = {"type": "error", "error": error_message}
    if session_id:
        message["session_id"] = session_id
    await websocket.send_json(message)


@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    qa_system = websocket.app.state.qa_system

    if qa_system is None:
        await send_websocket_error(websocket, "问答系统尚未就绪")
        await websocket.close(code=1013)
        return

    try:
        while True:
            session_id = None
            try:
                request_data = json.loads(await websocket.receive_text())
                if not isinstance(request_data, dict):
                    raise ValueError("请求数据必须是 JSON 对象")  # noqa: TRY004

                query_text = request_data.get("query")
                if not isinstance(query_text, str) or not query_text.strip():
                    raise ValueError("查询内容不能为空")

                query_text = query_text.strip()
                source_filter = request_data.get("source_filter")
                if isinstance(source_filter, str):
                    source_filter = source_filter.strip() or None
                elif source_filter is not None:
                    raise ValueError("source_filter 必须是字符串")

                validate_source_filter(source_filter, qa_system)
                session_id = request_data.get("session_id") or str(uuid.uuid4())
                start_time = time.perf_counter()

                await websocket.send_json(
                    {"type": "start", "session_id": session_id}
                )

                stream_completed = False
                query_iterator = qa_system.query(
                    query_text,
                    source_filter=source_filter,
                    session_id=session_id,
                )
                async for token, is_complete in iterate_in_threadpool(query_iterator):
                    if token:
                        await websocket.send_json(
                            {
                                "type": "token",
                                "token": token,
                                "session_id": session_id,
                            }
                        )
                    if is_complete:
                        stream_completed = True
                        await websocket.send_json(
                            {
                                "type": "end",
                                "session_id": session_id,
                                "is_complete": True,
                                "processing_time": time.perf_counter() - start_time,
                            }
                        )
                        break

                if not stream_completed:
                    await websocket.send_json(
                        {
                            "type": "end",
                            "session_id": session_id,
                            "is_complete": True,
                            "processing_time": time.perf_counter() - start_time,
                        }
                    )
            except WebSocketDisconnect:
                raise
            except json.JSONDecodeError:
                await send_websocket_error(
                    websocket,
                    "请求数据不是有效的 JSON",
                    session_id,
                )
            except ValueError as exception:
                await send_websocket_error(websocket, str(exception), session_id)
            except Exception:
                logger.exception("WebSocket 查询处理失败，session_id=%s", session_id)
                await send_websocket_error(websocket, "查询处理失败", session_id)
    except WebSocketDisconnect:
        logger.info("WebSocket 客户端已断开")
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
