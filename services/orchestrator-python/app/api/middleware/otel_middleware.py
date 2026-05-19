"""OpenTelemetry ASGI 中间件

实现完整的 ASGI 中间件，为每个请求创建 Span 并自动提取/注入 trace context。

【核心功能】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 自动为每个请求创建 Span
2. 提取上游传递的 W3C Trace Context（traceparent/tracestate）
3. 注入 trace context 到下游调用
4. 记录请求方法、路径、状态码等属性
5. 捕获并记录异常信息

【ASGI 中间件 vs BaseHTTPMiddleware】
┌─────────────────────────────────────────────────────────────────────────┐
│  BaseHTTPMiddleware  │  实现简单、类型友好       │  性能开销较高        │
│  ASGI Middleware     │  性能最优、原生支持       │  实现稍复杂          │
└─────────────────────────────────────────────────────────────────────────┘

本项目选择 ASGI 原生中间件，原因：
- 性能更优（无额外封装开销）
- 支持流式响应（SSE/WebSocket）
- 与 OpenTelemetry 自动埋点对齐

【使用方式】
    app = FastAPI()
    app.add_middleware(OtelMiddleware, service_name="orchestrator-python")

【参考】
- ASGI 规范: https://asgi.readthedocs.io/
- W3C Trace Context: https://www.w3.org/TR/trace-context/
- OpenTelemetry ASGI: https://opentelemetry-python.readthedocs.io/
"""

from __future__ import annotations

import typing

from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import Span, Status, StatusCode

if typing.TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

# W3C Trace Context header names
TRACEPARENT_HEADER = "traceparent"
TRACESTATE_HEADER = "tracestate"


class OtelMiddleware:
    """OpenTelemetry ASGI 中间件

    实现原生 ASGI 中间件，为每个请求创建 Span 并自动传播 trace context。

    Attributes:
        app: ASGI 应用实例
        service_name: 服务名称（用于资源标识）
        tracer: OpenTelemetry tracer 实例

    Example:
        >>> app = FastAPI()
        >>> app.add_middleware(OtelMiddleware, service_name="orchestrator-python")
    """

    def __init__(self, app: ASGIApp, service_name: str = "orchestrator-python") -> None:
        """初始化中间件

        Args:
            app: ASGI 应用实例
            service_name: 服务名称，用于 Span 资源标识
        """
        self.app = app
        self.service_name = service_name
        self.tracer = trace.get_tracer(service_name)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI 中间件入口点

        处理 HTTP 请求，创建 Span 并传播 trace context。

        Args:
            scope: ASGI scope 字典，包含请求信息
            receive: 接收请求体的 callable
            send: 发送响应的 callable

        Note:
            只处理 HTTP 请求（scope["type"] == "http"）。
            其他类型的请求（lifespan、websocket）直接透传。
        """
        # 只处理 HTTP 请求
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 提取 trace context（支持 W3C Trace Context 格式）
        headers = dict(scope.get("headers", []))
        carrier: dict[str, str] = {}

        # 将 bytes headers 转换为 str
        for key, value in headers.items():
            carrier[key.decode("latin1")] = value.decode("latin1")

        # 从请求头提取 trace context
        ctx = extract(carrier)

        # 获取请求信息
        method = scope["method"]
        path = scope["path"]
        query_string = scope.get("query_string", b"").decode("latin1")

        # 创建 Span 名称（格式：HTTP {method} {path}）
        span_name = f"HTTP {method} {path}"

        # 在提取的 context 中创建 Span
        with self.tracer.start_as_current_span(
            span_name,
            context=ctx,
            kind=trace.SpanKind.SERVER,
        ) as span:
            # 设置 Span 属性（遵循 OpenTelemetry 语义约定）
            self._set_http_attributes(span, scope)

            # 创建响应状态收集器
            response_status_code: int = 0
            response_headers: dict[str, str] = {}

            async def send_wrapper(message: Message) -> None:
                """包装 send callable 以捕获响应信息"""
                nonlocal response_status_code, response_headers

                if message["type"] == "http.response.start":
                    # 捕获响应状态码
                    response_status_code = message["status"]
                    # 捕获响应头
                    for key, value in message.get("headers", []):
                        header_key = key.decode("latin1") if isinstance(key, bytes) else key
                        header_value = value.decode("latin1") if isinstance(value, bytes) else value
                        response_headers[header_key] = header_value

                    # 注入 trace context 到响应头
                    inject_response_headers(message)

                await send(message)

            def inject_response_headers(message: Message) -> None:
                """将 trace context 注入到响应头"""
                # 创建 carrier dict 并注入 trace context
                carrier: dict[str, str] = {}
                inject(carrier)

                # 创建新的 headers 列表
                headers = list(message.get("headers", []))

                # 添加 traceparent header
                if "traceparent" in carrier:
                    headers.append((b"traceparent", carrier["traceparent"].encode("latin1")))

                message["headers"] = headers

            try:
                # 执行下游处理
                await self.app(scope, receive, send_wrapper)

                # 记录响应状态码
                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response_status_code)

                # 设置 Span 状态
                if response_status_code >= 500 or response_status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {response_status_code}"))
                else:
                    span.set_status(Status(StatusCode.OK))

            except Exception as exc:
                # 记录异常信息
                self._record_exception(span, exc)
                raise

    def _set_http_attributes(self, span: Span, scope: Scope) -> None:
        """设置 HTTP 相关 Span 属性

        遵循 OpenTelemetry 语义约定（Semantic Conventions）。

        Args:
            span: OpenTelemetry Span 实例
            scope: ASGI scope 字典
        """
        # 基础 HTTP 属性
        span.set_attribute(SpanAttributes.HTTP_METHOD, scope["method"])
        span.set_attribute(SpanAttributes.HTTP_URL, str(scope.get("root_path", "")) + scope["path"])
        span.set_attribute(SpanAttributes.HTTP_TARGET, scope["path"])
        span.set_attribute(SpanAttributes.HTTP_SCHEME, scope.get("scheme", "http"))

        # Host 信息
        headers = dict(scope.get("headers", []))
        host = headers.get(b"host", b"").decode("latin1")
        if host:
            span.set_attribute(SpanAttributes.NET_HOST_NAME, host.split(":")[0])
            if ":" in host:
                span.set_attribute(SpanAttributes.NET_HOST_PORT, int(host.split(":")[1]))

        # 请求头中的追踪标识
        request_id = headers.get(b"x-request-id", b"").decode("latin1")
        tenant_id = headers.get(b"x-tenant-id", b"").decode("latin1")
        user_id = headers.get(b"x-user-id", b"").decode("latin1")

        if request_id:
            span.set_attribute("request.id", request_id)
        if tenant_id:
            span.set_attribute("tenant.id", tenant_id)
        if user_id:
            span.set_attribute("user.id", user_id)

        # HTTP 版本
        http_version = scope.get("http_version", "1.1")
        span.set_attribute(SpanAttributes.HTTP_FLAVOR, http_version)

        # 服务信息
        span.set_attribute("service.name", self.service_name)

        # 客户端信息
        client = scope.get("client")
        if client:
            span.set_attribute(SpanAttributes.NET_PEER_NAME, client[0])
            span.set_attribute(SpanAttributes.NET_PEER_PORT, client[1])

    def _record_exception(self, span: Span, exc: Exception) -> None:
        """记录异常信息到 Span

        Args:
            span: OpenTelemetry Span 实例
            exc: 捕获的异常实例
        """
        # 记录异常堆栈
        span.record_exception(exc)

        # 设置错误属性
        span.set_attribute("error", True)
        span.set_attribute("error.type", exc.__class__.__name__)
        span.set_attribute("error.message", str(exc))

        # 设置 Span 状态为 ERROR
        span.set_status(Status(StatusCode.ERROR, str(exc)))
