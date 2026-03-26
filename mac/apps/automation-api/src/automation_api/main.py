"""
Automation API Server Main Entry
"""

import sys
import uvicorn
from fastapi import FastAPI, APIRouter

from automation_api.core.config import settings
from automation_api.core.deps import ApiKeyDep, OperationLockDep
from automation_api.schemas.messaging import (
    ApiResponse,
    SendByTitleRequest,
    SendMessageRequest,
    SessionItem,
    CurrentConversation,
)
from wechat_agent import WeChatService
from wework_agent import WeWorkService

app = FastAPI(
    title="Mac Automation API Layer",
    description="Workspace Unified API connecting WeChat & WeWork underlying agents.",
    version="0.1.0",
)

def create_platform_router(platform_name: str, service_class) -> APIRouter:
    router = APIRouter(prefix=f"/{platform_name}", tags=[platform_name.capitalize()])

    @router.get("/sessions", response_model=ApiResponse, summary="获取会话列表")
    async def list_sessions(_auth: ApiKeyDep, _lock: OperationLockDep, limit: int = 0):
        svc = service_class()
        result = svc.list_sessions(limit)
        if not result["ok"]:
            return ApiResponse(ok=False, message=result["message"])
        sessions = [
            SessionItem(index=s["index"], title=s["title"], texts=s["texts"])
            for s in result["sessions"]
        ]
        return ApiResponse(ok=True, message=f"共 {len(sessions)} 个会话", data=[s.model_dump() for s in sessions])

    @router.get("/current", response_model=ApiResponse, summary="获取当前会话")
    async def get_current(_auth: ApiKeyDep, _lock: OperationLockDep):
        svc = service_class()
        result = svc.get_current_conversation()
        if not result["ok"]:
            return ApiResponse(ok=False, message=result["message"])
        conv = CurrentConversation(title=result.get("title"))
        return ApiResponse(ok=True, message="获取成功", data=conv.model_dump())

    @router.post("/send", response_model=ApiResponse, summary="给当前会话发消息")
    async def send_message(body: SendMessageRequest, _auth: ApiKeyDep, _lock: OperationLockDep):
        svc = service_class()
        result = svc.send_current_chat(body.message)
        return ApiResponse(ok=result["ok"], message=result["message"], data=result.get("data"))

    @router.post("/send_by_title", response_model=ApiResponse, summary="按标题搜索并发消息")
    async def send_by_title(body: SendByTitleRequest, _auth: ApiKeyDep, _lock: OperationLockDep):
        svc = service_class()
        result = svc.send_by_title(body.title, body.message)
        return ApiResponse(ok=result["ok"], message=result["message"], data=result.get("data"))

    return router

app.include_router(create_platform_router("wechat", WeChatService))
app.include_router(create_platform_router("wework", WeWorkService))

@app.get("/health", response_model=ApiResponse, tags=["健康检查"])
async def health_check():
    from ax_core import check_accessibility_permission
    has_perm = check_accessibility_permission()
    return ApiResponse(
        ok=has_perm,
        message="Running correctly" if has_perm else "Accessibility Permission Missing",
        data={"accessibility_trusted": has_perm}
    )

def cli():
    uvicorn.run("automation_api.main:app", host="0.0.0.0", port=settings.port, reload=True)

if __name__ == "__main__":
    cli()
