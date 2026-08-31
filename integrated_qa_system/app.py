"""教育问答系统的 FastAPI 接口层。

本模块负责 HTTP、WebSocket、会话历史和静态前端资源服务，
具体的 FAQ 检索与 RAG 生成逻辑由 IntegratedQASystem 提供。
"""

from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
import re
import sys
import time
from typing import Any, Optional
import uuid

from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool
from starlette.websockets import WebSocketDisconnect, WebSocketState


# 使用 app.py 所在目录计算资源路径，避免启动目录变化导致静态文件失效。
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"

# 模块日志记录器和统一路由对象。
logger = logging.getLogger(__name__)
router = APIRouter()


# 常见日常用语直接返回固定答案，避免无意义地进入检索与大模型流程。
GREETING_PATTERNS = [
    {
        "pattern": r"^(你好|您好|hi|hello)",
        "response": "你好！我是涛小将，专注于为学生答疑解惑，很高兴为你服务！",
    },
    {
        "pattern": r"^(你是谁|您是谁|你叫什么|你的名字|who are you)",
        "response": "我是涛小将，你的智能学习助手，致力于提供 IT 教育相关的解答！",
    },
    {
        "pattern": r"^(在吗|在不在|有人吗)",
        "response": "我在！我是涛小将，随时为你解答问题！",
    },
    {
        "pattern": r"^(干嘛呢|你在干嘛|做什么)",
        "response": "我正在待命，随时为你解答 IT 学习相关的问题！有什么我可以帮你的？",
    },
]


class QueryRequest(BaseModel):
    """HTTP 非流式查询的请求数据。"""

    query: str
    source_filter: Optional[str] = None
    session_id: Optional[str] = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """清理查询文本并拒绝空白问题。"""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("查询内容不能为空")
        return normalized_value

    @field_validator("source_filter", "session_id")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        """将可选字符串统一为去除首尾空格后的值或 None。"""

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


def check_greeting(query: str) -> Optional[str]:
    """匹配预定义问候语，匹配成功时返回固定回复。"""

    query_text = query.strip()
    for pattern_info in GREETING_PATTERNS:
        if re.match(pattern_info["pattern"], query_text, re.IGNORECASE):
            return pattern_info["response"]
    return None


def _create_qa_system():
    """延迟导入并创建问答系统，避免模块导入时加载模型和外部连接。"""

    # 保留项目现有的绝对导入方式，使 uvicorn 从仓库根目录启动时也能找到模块。
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    from new_main import IntegratedQASystem

    return IntegratedQASystem()


def _close_qa_system(qa_system: Any) -> None:
    """关闭问答系统持有的 MySQL 和 Redis 连接。"""

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
    """管理问答系统从应用启动到关闭的完整生命周期。"""

    # 真实运行时在启动阶段初始化；测试可以预先注入 FakeQASystem 跳过外部服务。
    if app.state.qa_system is None:
        app.state.qa_system = await run_in_threadpool(_create_qa_system)
        app.state.owns_qa_system = True

    try:
        yield
    finally:
        # 只有应用自行创建的实例才由应用负责释放，避免关闭外部注入对象。
        if app.state.owns_qa_system and app.state.qa_system is not None:
            await run_in_threadpool(_close_qa_system, app.state.qa_system)


def _get_http_qa_system(request: Request):
    """从 FastAPI 应用状态中获取已初始化的问答系统。"""

    qa_system = request.app.state.qa_system
    if qa_system is None:
        raise HTTPException(status_code=503, detail="问答系统尚未就绪")
    return qa_system


def _validate_source_filter(source_filter: Optional[str], qa_system: Any) -> None:
    """校验前端传入的学科过滤条件是否在系统支持范围内。"""

    valid_sources = qa_system.config.VALID_SOURCES
    if source_filter and source_filter not in valid_sources:
        raise ValueError(f"无效的学科类别: {source_filter}")


async def _record_history(
    qa_system: Any,
    session_id: str,
    question: str,
    answer: str,
) -> None:
    """在线程池中写入会话历史，写入失败不影响本次答案返回。"""

    try:
        await run_in_threadpool(
            qa_system.update_session_history,
            session_id,
            question,
            answer,
        )
    except Exception:
        logger.exception("会话历史写入失败，session_id=%s", session_id)


@router.get("/", include_in_schema=False)
async def read_root():
    """返回前端首页；前端未生成时返回明确的 404 信息。"""

    if not INDEX_FILE.is_file():
        raise HTTPException(status_code=404, detail="前端页面尚未生成")
    return FileResponse(INDEX_FILE)


async def _create_session(qa_system: Any, title: str) -> dict:
    session_id = str(uuid.uuid4())
    return await run_in_threadpool(
        qa_system.create_session,
        session_id,
        title,
    )


@router.post("/api/create_session")
async def create_session(request: Request):
    """创建供前端保存和复用的唯一会话 ID。"""

    qa_system = _get_http_qa_system(request)
    return await _create_session(qa_system, "新的学习问题")


@router.post("/api/sessions")
async def create_named_session(
    request_data: SessionTitleRequest,
    request: Request,
):
    """创建并持久化一个前端会话。"""

    qa_system = _get_http_qa_system(request)
    return await _create_session(qa_system, request_data.title)


@router.get("/api/sessions")
async def list_sessions(request: Request):
    """返回最近使用的会话。"""

    qa_system = _get_http_qa_system(request)
    sessions = await run_in_threadpool(qa_system.list_sessions)
    return {"sessions": sessions}


@router.patch("/api/sessions/{session_id}")
async def rename_session(
    session_id: str,
    request_data: SessionTitleRequest,
    request: Request,
):
    """更新指定会话标题。"""

    qa_system = _get_http_qa_system(request)
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


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    """删除指定会话及其问答历史。"""

    qa_system = _get_http_qa_system(request)
    success = await run_in_threadpool(qa_system.delete_session, session_id)
    if not success:
        raise HTTPException(status_code=500, detail="删除会话失败")
    return {"status": "success", "message": "会话已删除"}


@router.get("/api/history/{session_id}")
async def get_history(session_id: str, request: Request):
    """查询指定会话最近保留的问答历史。"""

    qa_system = _get_http_qa_system(request)
    try:
        # 现有 MySQL 客户端是同步实现，因此放入线程池避免阻塞事件循环。
        history = await run_in_threadpool(
            qa_system.get_session_history,
            session_id,
        )
        return {"session_id": session_id, "history": history}
    except Exception as exception:
        logger.exception("获取历史记录失败，session_id=%s", session_id)
        raise HTTPException(status_code=500, detail="获取历史记录失败") from exception


@router.delete("/api/history/{session_id}")
async def clear_history(session_id: str, request: Request):
    """删除指定会话的全部历史记录。"""

    qa_system = _get_http_qa_system(request)
    success = await run_in_threadpool(
        qa_system.clear_session_history,
        session_id,
    )
    if not success:
        raise HTTPException(status_code=500, detail="清除历史记录失败")
    return {"status": "success", "message": "历史记录已清除"}


@router.post("/api/query", response_model=QueryResponse)
async def query(request_data: QueryRequest, request: Request):
    """处理问候语和 FAQ 查询，并告知前端是否需要切换 WebSocket。"""

    start_time = time.perf_counter()
    qa_system = _get_http_qa_system(request)
    session_id = request_data.session_id or str(uuid.uuid4())

    # 学科过滤由后端统一校验，防止前端传入未知知识库类别。
    try:
        _validate_source_filter(request_data.source_filter, qa_system)
    except ValueError as exception:
        raise HTTPException(status_code=400, detail=str(exception)) from exception

    # 日常问候直接回复，不执行 BM25 和 RAG 查询。
    greeting_response = check_greeting(request_data.query)
    if greeting_response:
        await _record_history(
            qa_system,
            session_id,
            request_data.query,
            greeting_response,
        )
        return {
            "answer": greeting_response,
            "is_streaming": False,
            "session_id": session_id,
            "processing_time": time.perf_counter() - start_time,
        }

    # BM25、Redis 和 MySQL 都是同步调用，通过线程池执行以保护异步服务线程。
    answer, need_rag = await run_in_threadpool(
        qa_system.bm25_search.search,
        request_data.query,
        0.85,
    )

    # HTTP 接口不执行耗时的 RAG 生成，前端收到标志后改用 WebSocket。
    if need_rag:
        return {
            "answer": "请使用WebSocket接口获取流式响应",
            "is_streaming": True,
            "session_id": session_id,
            "processing_time": time.perf_counter() - start_time,
        }

    # FAQ 命中或明确无答案时，直接返回并记录本轮会话。
    response_answer = answer or "未找到答案"
    await _record_history(
        qa_system,
        session_id,
        request_data.query,
        response_answer,
    )
    return {
        "answer": response_answer,
        "is_streaming": False,
        "session_id": session_id,
        "processing_time": time.perf_counter() - start_time,
    }


async def _send_websocket_error(
    websocket: WebSocket,
    error_message: str,
    session_id: Optional[str] = None,
) -> None:
    """在连接仍然有效时向前端发送统一 WebSocket 错误消息。"""

    if websocket.client_state != WebSocketState.CONNECTED:
        return

    message = {"type": "error", "error": error_message}
    if session_id:
        message["session_id"] = session_id
    await websocket.send_json(message)


@router.websocket("/api/stream")
async def websocket_endpoint(websocket: WebSocket):
    """接收查询并按照 start、token、end 或 error 协议返回消息。"""

    await websocket.accept()
    qa_system = websocket.app.state.qa_system

    # 服务尚未完成初始化时使用 1013 告知客户端稍后重试。
    if qa_system is None:
        await _send_websocket_error(websocket, "问答系统尚未就绪")
        await websocket.close(code=1013)
        return

    try:
        while True:
            session_id = None
            try:
                # 每条客户端消息都必须是包含 query 的 JSON 对象。
                request_data = json.loads(await websocket.receive_text())
                if not isinstance(request_data, dict):
                    raise ValueError("请求数据必须是 JSON 对象")

                query_text = request_data.get("query")
                if not isinstance(query_text, str) or not query_text.strip():
                    raise ValueError("查询内容不能为空")

                query_text = query_text.strip()
                source_filter = request_data.get("source_filter")
                if isinstance(source_filter, str):
                    source_filter = source_filter.strip() or None
                elif source_filter is not None:
                    raise ValueError("source_filter 必须是字符串")

                _validate_source_filter(source_filter, qa_system)
                session_id = request_data.get("session_id") or str(uuid.uuid4())
                start_time = time.perf_counter()

                # start 消息用于通知前端创建机器人消息占位和加载状态。
                await websocket.send_json(
                    {"type": "start", "session_id": session_id}
                )

                # 问候语也遵循统一的 token 和 end 消息协议。
                greeting_response = check_greeting(query_text)
                if greeting_response:
                    await websocket.send_json(
                        {
                            "type": "token",
                            "token": greeting_response,
                            "session_id": session_id,
                        }
                    )
                    await _record_history(
                        qa_system,
                        session_id,
                        query_text,
                        greeting_response,
                    )
                    await websocket.send_json(
                        {
                            "type": "end",
                            "session_id": session_id,
                            "is_complete": True,
                            "processing_time": time.perf_counter() - start_time,
                        }
                    )
                    continue

                # 现有 query 是同步生成器，iterate_in_threadpool 可避免阻塞事件循环。
                stream_completed = False
                query_iterator = qa_system.query(
                    query_text,
                    source_filter=source_filter,
                    session_id=session_id,
                )
                async for token, is_complete in iterate_in_threadpool(query_iterator):
                    # token 可能是 FAQ 完整答案，也可能是 RAG 的分段内容。
                    if token:
                        await websocket.send_json(
                            {
                                "type": "token",
                                "token": token,
                                "session_id": session_id,
                            }
                        )
                    # is_complete=True 表示本轮生成结束，前端可停止加载动画。
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

                # 防御性处理：生成器正常结束但没有主动发送完成标志时补发 end。
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
                await _send_websocket_error(
                    websocket,
                    "请求数据不是有效的 JSON",
                    session_id,
                )
            except ValueError as exception:
                await _send_websocket_error(websocket, str(exception), session_id)
            except Exception:
                logger.exception("WebSocket 查询处理失败，session_id=%s", session_id)
                await _send_websocket_error(
                    websocket,
                    "查询处理失败",
                    session_id,
                )
    except WebSocketDisconnect:
        # 客户端主动关闭属于正常流程，只记录状态而不返回错误。
        logger.info("WebSocket 客户端已断开")
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()


@router.get("/health")
async def health_check():
    """供部署平台和监控系统检查 HTTP 服务是否存活。"""

    return {"status": "healthy"}


@router.get("/api/sources")
async def get_sources(request: Request):
    """返回前端学科筛选组件可展示的有效类别。"""

    qa_system = _get_http_qa_system(request)
    return {"sources": qa_system.config.VALID_SOURCES}


@router.get(
    "/api/faq/suggestions",
    response_model=FAQSuggestionResponse,
)
async def get_faq_suggestions(request: Request):
    """从 Redis 或 MySQL 获取前端“试着问”问题。"""

    qa_system = _get_http_qa_system(request)
    try:
        suggestions = await run_in_threadpool(
            qa_system.query_faq_suggestions
        )
        return {"suggestions": suggestions}
    except Exception as exception:
        logger.exception("获取 FAQ 推荐问题失败")
        raise HTTPException(
            status_code=500,
            detail="获取推荐问题失败",
        ) from exception


def create_app(qa_system: Any = None) -> FastAPI:
    """创建 FastAPI 应用，支持生产初始化和测试依赖注入。"""

    application = FastAPI(
        title="问答系统API",
        description="集成MySQL和RAG的智能问答系统",
        lifespan=lifespan,
    )
    application.state.qa_system = qa_system
    application.state.owns_qa_system = False

    # 当前配置便于本地前后端联调，生产环境应将来源限制为实际前端域名。
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 提前创建静态目录，后续生成 WebUI 后无需修改后端挂载逻辑。
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    application.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )
    application.include_router(router)
    return application


# uvicorn 导入 integrated_qa_system.app:app 时使用的默认应用实例。
app = create_app()


if __name__ == "__main__":
    import uvicorn

    # 允许直接执行 app.py 启动本地服务。
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
