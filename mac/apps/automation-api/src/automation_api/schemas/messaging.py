"""
Messaging Schemas
"""

from typing import Any, List, Optional
from pydantic import BaseModel, Field

class SessionItem(BaseModel):
    index: int = Field(..., description="会话位置编号")
    title: str = Field(..., description="会话标题")
    texts: List[str] = Field(default_factory=list, description="相关文本数组")

class CurrentConversation(BaseModel):
    title: Optional[str] = Field(None, description="当前打开的会话标题")

class SendMessageRequest(BaseModel):
    message: str = Field(..., description="要发送的消息文本")

class SendByTitleRequest(BaseModel):
    title: str = Field(..., description="目标会话标题（完整匹配）")
    message: str = Field(..., description="要发送的消息文本")

class ApiResponse(BaseModel):
    ok: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="状态描述")
    data: Optional[Any] = Field(None, description="详细数据返回")
