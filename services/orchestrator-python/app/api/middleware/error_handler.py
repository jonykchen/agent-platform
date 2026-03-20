"""Error handler middleware - 统一异常处理"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import structlog

from app.api.middleware.request_context import get_request_id
from app.core.exceptions import BasePlatformException

logger = structlog.get_logger()


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Error handler middleware"""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except BasePlatformException as e:
            logger.warning(
                "Business exception",
                error_code=e.code,
                message=e.message,
                request_id=get_request_id(),
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": e.code,
                    "message": e.message,
                    "user_message": e.user_message,
                    "request_id": get_request_id(),
                    "details": e.details,
                },
            )
        except Exception as e:
            logger.error(
                "Unexpected error",
                error=str(e),
                request_id=get_request_id(),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "ERR_UNKNOWN",
                    "message": "Internal server error",
                    "user_message": "服务器内部错误，请稍后重试",
                    "request_id": get_request_id(),
                },
            )