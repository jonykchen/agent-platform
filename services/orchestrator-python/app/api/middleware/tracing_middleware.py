"""追踪中间件 - 将 OpenTelemetry trace_id 注入到请求上下文"""

from __future__ import annotations

from fastapi import Request
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.middleware.request_context import _trace_id


class TracingMiddleware(BaseHTTPMiddleware):
    """追踪中间件

    功能：
    1. 自动为每个请求创建 span
    2. 提取上游传递的 trace context
    3. 将 trace_id 注入到 request context
    4. 记录请求基本信息（方法、路径、状态码）
    """

    async def dispatch(self, request: Request, call_next):
        tracer = trace.get_tracer(__name__)

        # 从请求头提取 trace context（支持 W3C Trace Context）
        traceparent = request.headers.get("traceparent", "")

        # 创建 span
        with tracer.start_as_current_span(
            f"HTTP {request.method} {request.url.path}",
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.scheme": request.url.scheme,
                "http.host": request.url.hostname or "",
                "http.target": request.url.path,
            },
        ) as span:
            # 注入 trace_id 到 context
            # NOTE: Use get_span_context() instead of span.context —
            # NonRecordingSpan (used when OTel is not initialized) lacks .context
            ctx = span.get_span_context()
            trace_id = format(ctx.trace_id, "032x")
            span_id = format(ctx.span_id, "016x")

            # 设置到请求上下文
            _trace_id.set(trace_id)

            # 设置 span 属性
            span.set_attribute("request_id", request.headers.get("X-Request-ID", ""))
            span.set_attribute("tenant_id", request.headers.get("X-Tenant-ID", ""))
            span.set_attribute("user_id", request.headers.get("X-User-ID", "anonymous"))

            try:
                # 执行请求
                response = await call_next(request)

                # 记录响应信息
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.response_content_length", response.headers.get("content-length", "0"))

                if response.status_code >= 400:
                    span.set_attribute("error", True)

                return response

            except Exception as exc:
                # 记录异常
                span.record_exception(exc)
                span.set_attribute("error", True)
                span.set_attribute("error.type", exc.__class__.__name__)
                raise
