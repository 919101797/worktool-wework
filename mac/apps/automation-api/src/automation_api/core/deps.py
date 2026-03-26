"""
API Dependency Injection (API Key + Operation Lock)
"""

import asyncio
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_api_key(api_key: str = Security(api_key_header)) -> str | None:
    if settings.api_key:
        if not api_key or api_key != settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key",
            )
    return api_key

ApiKeyDep = Annotated[str | None, Depends(get_api_key)]

# Global Async Lock for GUI automation
# Crucial: Ensures that macOS accessibility (mouse/keyboard simulate) isn't executed concurrently.
_operation_lock = asyncio.Lock()

async def get_operation_lock() -> None:
    async with _operation_lock:
        yield

OperationLockDep = Annotated[None, Depends(get_operation_lock)]
