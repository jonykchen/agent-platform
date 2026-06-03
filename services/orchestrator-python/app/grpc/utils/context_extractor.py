"""RequestContext 提取工具

从 gRPC 请求中提取上下文信息。

【核心概念】gRPC 元数据传递
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Gateway Java 在调用 Orchestrator 时，通过 RequestContext 传递：
- request_id: 全链路追踪 ID
- tenant_id: 租户 ID（多租户隔离）
- user_id: 用户 ID
- trace_id: OpenTelemetry Trace ID
- session_id: 会话 ID（可选）

提取后的上下文用于：
1. 日志记录（关联请求）
2. 权限校验（租户隔离）
3. OpenTelemetry 追踪
"""

from typing import Dict, Optional

import structlog

from app.gen.gateway import orchestrator_pb2

logger = structlog.get_logger()


def extract_context_from_request(
    context: orchestrator_pb2.RequestContext,
) -> Dict[str, Optional[str]]:
    """从 RequestContext 提取上下文信息

    Args:
        context: gRPC RequestContext 消息

    Returns:
        包含 request_id, tenant_id, user_id, trace_id, session_id 的字典
    """
    return {
        "request_id": context.request_id or None,
        "tenant_id": context.tenant_id or None,
        "user_id": context.user_id or None,
        "trace_id": context.trace_id or None,
        "session_id": context.session_id or None,
        "channel": context.channel or None,
    }


def extract_context_from_metadata(
    metadata: list,
) -> Dict[str, Optional[str]]:
    """从 gRPC 元数据提取上下文信息

    Args:
        metadata: gRPC 元数据列表 [(key, value), ...]

    Returns:
        包含 request_id, tenant_id, user_id 的字典
    """
    metadata_dict = dict(metadata)

    return {
        "request_id": metadata_dict.get("x-request-id") or metadata_dict.get("request_id"),
        "tenant_id": metadata_dict.get("x-tenant-id") or metadata_dict.get("tenant_id"),
        "user_id": metadata_dict.get("x-user-id") or metadata_dict.get("user_id"),
    }


def get_session_id_from_request(
    request: orchestrator_pb2.ChatRequest,
) -> Optional[str]:
    """从 ChatRequest 获取 session_id

    session_id 可能在两个位置：
    1. request.context.session_id（优先）
    2. 如果为空，可能需要新建

    Args:
        request: ChatRequest 消息

    Returns:
        session_id 或 None
    """
    if request.context.session_id:
        return request.context.session_id
    return None
