from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """兼容原有存活检查。"""

    return {"status": "healthy"}


@router.get("/health/live")
async def liveness_check():
    """仅表示 HTTP 进程仍可响应。"""

    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_check(request: Request):
    """确认问答系统已完成生命周期初始化。"""

    if request.app.state.qa_system is None:
        raise HTTPException(status_code=503, detail="问答系统尚未就绪")
    return {"status": "ready"}
