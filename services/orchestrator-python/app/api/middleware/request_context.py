"""Request context middleware - request_id / tenant_id / user_id 注入"""

from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Context variables for request context
_request_id: ContextVar[str] = ContextVar("request_id", default="")
_tenant_id: ContextVar[str] = ContextVar("tenant_id", default="")
_user_id: ContextVar[str] = ContextVar("user_id", default="")
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")


def get_request_id(default: str = "") -> str:
    return _request_id.get(default)


def get_tenant_id(default: str = "") -> str:
    return _tenant_id.get(default)


def get_user_id(default: str = "") -> str:
    return _user_id.get(default)


def get_trace_id(default: str = "") -> str:
    return _trace_id.get(default)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Request context middleware"""

    async def dispatch(self, request: Request, call_next):
        # Extract headers
        request_id = request.headers.get("X-Request-ID", "")
        tenant_id = request.headers.get("X-Tenant-ID", "")
        user_id = request.headers.get("X-User-ID", "anonymous")
        trace_id = request.headers.get("X-Trace-ID", "")

        # Set context variables
        _request_id.set(request_id)
        _tenant_id.set(tenant_id)
        _user_id.set(user_id)
        _trace_id.set(trace_id)

        # Continue processing
        response = await call_next(request)

        # Add headers to response
        if request_id:
            response.headers["X-Request-ID"] = request_id

        return response