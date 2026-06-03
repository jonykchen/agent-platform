"""gRPC 追踪拦截器

为每个 gRPC 调用创建 OpenTelemetry Span，提取/注入 trace context。

【核心概念】OpenTelemetry gRPC 埋点
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

gRPC 拦截器可以在请求进入时：
1. 从元数据提取 traceparent（W3C Trace Context）
2. 创建 Span 作为当前上下文
3. 设置属性（rpc.system, rpc.method, request.id）
4. 记录异常

【参考】
- OpenTelemetry gRPC 埋点: https://opentelemetry-python.readthedocs.io/en/latest/instrumentation/grpc.html
- W3C Trace Context: https://www.w3.org/TR/trace-context/
"""

from typing import Callable, Any

import grpc
from grpc import aio
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.semconv.trace import SpanAttributes

import structlog

logger = structlog.get_logger()


class TracingInterceptor:
    """OpenTelemetry 追踪拦截器

    功能：
    1. 从 gRPC 元数据提取 trace context
    2. 创建 Span
    3. 记录请求属性
    4. 捕获异常

    使用方式：
    ```python
    server = aio.server(interceptors=[TracingInterceptor()])
    ```
    """

    def __init__(self, service_name: str = "orchestrator-python"):
        self.service_name = service_name
        self.tracer = trace.get_tracer(service_name)

    async def intercept_service(
        self,
        continuation: Callable,
        handler_call_details: Any,
    ):
        """拦截 gRPC 调用

        Args:
            continuation: 继续处理的函数
            handler_call_details: 调用详情

        Returns:
            RPC 方法处理器
        """
        # 提取元数据
        metadata = {}
        if hasattr(handler_call_details, 'invocation_metadata') and handler_call_details.invocation_metadata:
            metadata = dict(handler_call_details.invocation_metadata)

        # 提取 trace context（W3C Trace Context 格式）
        carrier = {}
        if "traceparent" in metadata:
            carrier["traceparent"] = metadata["traceparent"]
        if "tracestate" in metadata:
            carrier["tracestate"] = metadata["tracestate"]

        # 提取上下文
        ctx = extract(carrier)

        # 获取方法名
        method = getattr(handler_call_details, 'method', '') or ""

        # 创建 Span
        span_name = f"gRPC {method}"
        with self.tracer.start_as_current_span(
            span_name,
            context=ctx,
            kind=trace.SpanKind.SERVER,
        ) as span:
            # 设置标准属性
            span.set_attribute(SpanAttributes.RPC_SYSTEM, "grpc")
            span.set_attribute(SpanAttributes.RPC_METHOD, method)
            span.set_attribute(SpanAttributes.RPC_SERVICE, self.service_name)

            # 提取 request_id 并设置属性
            request_id = metadata.get("x-request-id") or metadata.get("request_id", "")
            if request_id:
                span.set_attribute("request.id", request_id)
                structlog.contextvars.bind_contextvars(request_id=request_id)

            # 提取 tenant_id
            tenant_id = metadata.get("x-tenant-id") or metadata.get("tenant_id", "")
            if tenant_id:
                span.set_attribute("tenant.id", tenant_id)
                structlog.contextvars.bind_contextvars(tenant_id=tenant_id)

            logger.debug(
                "grpc_request_received",
                method=method,
                request_id=request_id,
                tenant_id=tenant_id,
            )

            # 执行实际处理
            try:
                handler = await continuation(handler_call_details)
                span.set_attribute("rpc.grpc.status_code", grpc.StatusCode.OK.name[0])
                return handler

            except aio.AioRpcError as exc:
                # gRPC 错误
                span.record_exception(exc)
                span.set_attribute("error", True)
                span.set_attribute("rpc.grpc.status_code", exc.code().name[0])
                raise

            except Exception as exc:
                # 其他异常
                span.record_exception(exc)
                span.set_attribute("error", True)
                span.set_attribute("rpc.grpc.status_code", grpc.StatusCode.INTERNAL.name[0])
                raise

            finally:
                structlog.contextvars.unbind_contextvars("request_id", "tenant_id")
