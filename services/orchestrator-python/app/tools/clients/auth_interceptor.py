"""gRPC 认证拦截器 (S-06)

实现服务间认证：
- 客户端：注入 Service Token 和追踪信息
- 服务端：验证 Token 和服务身份
"""

from __future__ import annotations

import time
from typing import Callable

import grpc
import structlog

logger = structlog.get_logger()


class AuthInterceptor(grpc.UnaryUnaryClientInterceptor):
    """gRPC 客户端认证拦截器

    自动注入：
    - authorization: Service Token
    - x-service-name: 调用方服务名
    - x-request-id: 请求追踪 ID
    - x-tenant-id: 租户 ID

    使用方式:
        token_provider = lambda: get_service_token()
        interceptor = AuthInterceptor(
            service_name="orchestrator",
            token_provider=token_provider,
        )
        channel = grpc.insecure_channel("localhost:50051")
        intercepted_channel = grpc.intercept_channel(channel, interceptor)
    """

    def __init__(
        self,
        service_name: str,
        token_provider: Callable[[], str],
        request_id_provider: Callable[[], str] | None = None,
        tenant_id_provider: Callable[[], str] | None = None,
    ):
        self.service_name = service_name
        self.token_provider = token_provider
        self.request_id_provider = request_id_provider
        self.tenant_id_provider = tenant_id_provider

    def intercept_unary_unary(
        self,
        continuation: Callable,
        client_call_details: grpc.ClientCallDetails,
        request,
    ):
        """拦截一元调用，注入认证信息"""
        metadata = list(client_call_details.metadata or [])

        # 注入 Service Token
        token = self.token_provider()
        metadata.append(("authorization", f"Bearer {token}"))

        # 注入服务标识
        metadata.append(("x-service-name", self.service_name))

        # 注入请求追踪 ID
        if self.request_id_provider:
            request_id = self.request_id_provider()
            if request_id:
                metadata.append(("x-request-id", request_id))

        # 注入租户 ID
        if self.tenant_id_provider:
            tenant_id = self.tenant_id_provider()
            if tenant_id:
                metadata.append(("x-tenant-id", tenant_id))

        # 创建新的 ClientCallDetails
        new_details = client_call_details._replace(metadata=metadata)

        return continuation(new_details, request)


class ServerAuthInterceptor(grpc.ServerInterceptor):
    """gRPC 服务端认证拦截器

    验证：
    - Service Token 签名和有效期
    - 调用方服务身份（白名单）

    使用方式:
        interceptor = ServerAuthInterceptor(
            valid_services={"orchestrator", "gateway"},
            token_validator=validate_service_token,
        )
        server = grpc.server(futures.ThreadPoolExecutor(), interceptors=[interceptor])
    """

    def __init__(
        self,
        valid_services: set[str],
        token_validator: Callable[[str], dict],
        skip_methods: set[str] | None = None,
    ):
        """
        Args:
            valid_services: 合法的调用方服务名称集合
            token_validator: 验证 Token 并返回 payload 的函数
            skip_methods: 跳过认证的方法名（如健康检查）
        """
        self.valid_services = valid_services
        self.token_validator = token_validator
        self.skip_methods = skip_methods or {"grpc.health.v1.Health/Check"}

    def intercept_service(self, continuation, handler_call_details):
        """拦截服务调用，验证认证信息"""
        method = handler_call_details.method

        # 跳过指定方法
        if method in self.skip_methods:
            return continuation(handler_call_details)

        metadata = dict(handler_call_details.invocation_metadata or [])

        # 1. 提取并验证 Token
        auth_header = metadata.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid authorization header", method=method)
            return self._unauthenticated_handler("Missing authorization header")

        token = auth_header[7:]  # 去掉 "Bearer " 前缀

        try:
            payload = self.token_validator(token)
        except Exception as e:
            logger.warning("Token validation failed", method=method, error=str(e))
            return self._unauthenticated_handler("Invalid token")

        # 2. 验证服务身份
        service_name = metadata.get("x-service-name", "")
        if service_name not in self.valid_services:
            logger.warning(
                "Unauthorized service",
                method=method,
                service_name=service_name,
                valid_services=self.valid_services,
            )
            return self._permission_denied_handler(f"Unauthorized service: {service_name}")

        # 3. 记录审计日志
        logger.info(
            "gRPC call authenticated",
            method=method,
            service_name=service_name,
            request_id=metadata.get("x-request-id", ""),
            tenant_id=metadata.get("x-tenant-id", ""),
        )

        return continuation(handler_call_details)

    def _unauthenticated_handler(self, message: str):
        """返回未认证错误"""
        def abort_handler(request, context):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, message)
        return grpc.unary_unary_rpc_method_handler(abort_handler)

    def _permission_denied_handler(self, message: str):
        """返回权限拒绝错误"""
        def abort_handler(request, context):
            context.abort(grpc.StatusCode.PERMISSION_DENIED, message)
        return grpc.unary_unary_rpc_method_handler(abort_handler)


class ServiceTokenManager:
    """Service Token 管理器

    负责生成和验证服务间通信的 Token。
    使用 HMAC-SHA256 签名。
    """

    def __init__(
        self,
        secret: str,
        expiry_seconds: int = 300,  # 5 分钟
        issuer: str = "agent-platform",
    ):
        self.secret = secret.encode()
        self.expiry_seconds = expiry_seconds
        self.issuer = issuer

    def generate_token(self, service_name: str) -> str:
        """生成 Service Token

        Token 格式: base64(json(payload)) + "." + base64(signature)
        """
        import base64
        import hashlib
        import hmac
        import json

        now = int(time.time())
        payload = {
            "iss": self.issuer,
            "sub": service_name,
            "iat": now,
            "exp": now + self.expiry_seconds,
        }

        payload_json = json.dumps(payload, separators=(",", ":"))
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")

        signature = hmac.new(
            self.secret,
            payload_b64.encode(),
            hashlib.sha256,
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        return f"{payload_b64}.{signature_b64}"

    def validate_token(self, token: str) -> dict:
        """验证 Service Token

        Returns:
            Token payload

        Raises:
            ValueError: Token 无效或过期
        """
        import base64
        import hashlib
        import hmac
        import json

        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Invalid token format")

        payload_b64, signature_b64 = parts

        # 验证签名
        expected_signature = hmac.new(
            self.secret,
            payload_b64.encode(),
            hashlib.sha256,
        ).digest()

        # 补齐 base64 padding
        signature_b64_padded = signature_b64 + "=" * (4 - len(signature_b64) % 4)
        actual_signature = base64.urlsafe_b64decode(signature_b64_padded)

        if not hmac.compare_digest(expected_signature, actual_signature):
            raise ValueError("Invalid signature")

        # 解析 payload
        payload_b64_padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64_padded)
        payload = json.loads(payload_json)

        # 验证过期时间
        now = int(time.time())
        if payload.get("exp", 0) < now:
            raise ValueError("Token expired")

        # 验证签发者
        if payload.get("iss") != self.issuer:
            raise ValueError("Invalid issuer")

        return payload
