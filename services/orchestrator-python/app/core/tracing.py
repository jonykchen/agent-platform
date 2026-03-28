"""OpenTelemetry 追踪配置模块

配置分布式追踪，将 trace 数据发送到 OTel Collector。
支持跨服务追踪链路完整。

使用方式：
    from app.core.tracing import setup_tracing, get_tracer
    setup_tracing("orchestrator-python")
    tracer = get_tracer(__name__)
"""

from __future__ import annotations

import os
from typing import Optional

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = structlog.get_logger()

# Global tracer
_tracer: Optional[trace.Tracer] = None


def setup_tracing(
    service_name: str,
    otlp_endpoint: Optional[str] = None,
    sample_rate: float = 1.0,
) -> None:
    """初始化 OpenTelemetry 追踪

    Args:
        service_name: 服务名称（用于标识追踪链路）
        otlp_endpoint: OTel Collector 地址（默认从环境变量读取）
        sample_rate: 采样率（0.0-1.0，生产环境建议 0.1）
    """
    global _tracer

    # 从环境变量获取配置
    endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    enabled = os.getenv("OTEL_TRACING_ENABLED", "true").lower() == "true"

    if not enabled:
        logger.info("Tracing disabled", service_name=service_name)
        _tracer = trace.NoOpTracer()
        return

    # 创建资源（服务标识）
    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
        "deployment.environment": os.getenv("ENVIRONMENT", "production"),
    })

    # 创建 TracerProvider
    provider = TracerProvider(resource=resource)

    # 配置 OTLP 导出器
    otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # 设置全局 TracerProvider
    trace.set_tracer_provider(provider)

    # 创建 tracer
    _tracer = trace.get_tracer(service_name)

    # 自动埋点
    try:
        FastAPIInstrumentor.instrument()
        HTTPXClientInstrumentor.instrument()
        logger.info("Auto-instrumentation enabled", service_name=service_name)
    except Exception as e:
        logger.warning("Auto-instrumentation failed", error=str(e))

    logger.info(
        "Tracing initialized",
        service_name=service_name,
        endpoint=endpoint,
        sample_rate=sample_rate,
    )


def get_tracer(name: str = __name__) -> trace.Tracer:
    """获取 tracer 实例"""
    if _tracer is None:
        raise RuntimeError("Tracing not initialized, call setup_tracing() first")
    return _tracer


def shutdown_tracing() -> None:
    """关闭追踪（应用退出时调用）"""
    try:
        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, "shutdown"):
            tracer_provider.shutdown()
        logger.info("Tracing shutdown completed")
    except Exception as e:
        logger.warning("Tracing shutdown failed", error=str(e))


def get_current_trace_id() -> str:
    """获取当前 trace ID（用于日志关联）"""
    span = trace.get_current_span()
    if span and span.context:
        return format(span.context.trace_id, "032x")
    return ""


def get_current_span_id() -> str:
    """获取当前 span ID"""
    span = trace.get_current_span()
    if span and span.context:
        return format(span.context.span_id, "016x")
    return ""


class TracingContext:
    """追踪上下文管理器

    用于手动创建 span 并管理追踪上下文。

    Example:
        with TracingContext("tool_execution", tool_name="query_order") as ctx:
            result = execute_tool()
            ctx.set_attribute("result.status", "success")
    """

    def __init__(self, operation_name: str, **attributes):
        self.operation_name = operation_name
        self.attributes = attributes
        self.span = None

    def __enter__(self):
        tracer = get_tracer()
        self.span = tracer.start_span(self.operation_name)
        for key, value in self.attributes.items():
            self.span.set_attribute(key, value)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            if exc_type:
                self.span.record_exception(exc_val)
                self.span.set_attribute("error", True)
            self.span.end()

    def set_attribute(self, key: str, value) -> None:
        """设置 span 属性"""
        if self.span:
            self.span.set_attribute(key, value)

    def add_event(self, name: str, **attributes) -> None:
        """添加 span 事件"""
        if self.span:
            self.span.add_event(name, attributes)