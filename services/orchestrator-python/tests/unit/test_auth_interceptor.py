"""gRPC 认证拦截器测试"""

import pytest

from app.tools.clients.auth_interceptor import (
    AuthInterceptor,
    ServerAuthInterceptor,
    ServiceTokenManager,
)


class TestServiceTokenManager:
    """ServiceTokenManager 测试"""

    @pytest.fixture
    def token_manager(self):
        return ServiceTokenManager(
            secret="test-secret-key-32-chars-long!!!",
            expiry_seconds=300,
            issuer="agent-platform",
        )

    def test_generate_token(self, token_manager):
        """测试生成 Token"""
        token = token_manager.generate_token("orchestrator")

        assert token is not None
        assert "." in token  # payload.signature 格式
        parts = token.split(".")
        assert len(parts) == 2

    def test_validate_valid_token(self, token_manager):
        """测试验证有效 Token"""
        token = token_manager.generate_token("orchestrator")
        payload = token_manager.validate_token(token)

        assert payload["iss"] == "agent-platform"
        assert payload["sub"] == "orchestrator"
        assert "exp" in payload
        assert "iat" in payload

    def test_validate_invalid_signature(self, token_manager):
        """测试验证无效签名"""
        token = token_manager.generate_token("orchestrator")
        # 篡改 token
        parts = token.split(".")
        tampered_token = parts[0] + ".invalidsignature"

        with pytest.raises(ValueError, match="Invalid signature"):
            token_manager.validate_token(tampered_token)

    def test_validate_expired_token(self, token_manager):
        """测试验证过期 Token"""
        # 创建一个已过期的 manager
        expired_manager = ServiceTokenManager(
            secret="test-secret-key-32-chars-long!!!",
            expiry_seconds=-1,  # 立即过期
            issuer="agent-platform",
        )

        token = expired_manager.generate_token("orchestrator")

        with pytest.raises(ValueError, match="Token expired"):
            expired_manager.validate_token(token)

    def test_validate_invalid_issuer(self, token_manager):
        """测试验证无效签发者"""
        invalid_issuer_manager = ServiceTokenManager(
            secret="test-secret-key-32-chars-long!!!",
            expiry_seconds=300,
            issuer="wrong-issuer",
        )

        token = token_manager.generate_token("orchestrator")

        with pytest.raises(ValueError, match="Invalid issuer"):
            invalid_issuer_manager.validate_token(token)


class TestAuthInterceptor:
    """AuthInterceptor 测试"""

    def test_interceptor_creation(self):
        """测试拦截器创建"""
        interceptor = AuthInterceptor(
            service_name="orchestrator",
            token_provider=lambda: "test-token",
        )

        assert interceptor.service_name == "orchestrator"
        assert interceptor.token_provider() == "test-token"


class MockClientCallDetails:
    """Mock ClientCallDetails"""

    def __init__(self, metadata=None):
        self.metadata = metadata or []

    def _replace(self, metadata=None):
        return MockClientCallDetails(metadata)


class TestServerAuthInterceptor:
    """ServerAuthInterceptor 测试"""

    @pytest.fixture
    def token_manager(self):
        return ServiceTokenManager(
            secret="test-secret-key-32-chars-long!!!",
            expiry_seconds=300,
            issuer="agent-platform",
        )

    @pytest.fixture
    def interceptor(self, token_manager):
        return ServerAuthInterceptor(
            valid_services={"orchestrator", "gateway"},
            token_validator=token_manager.validate_token,
        )

    def test_interceptor_creation(self, interceptor):
        """测试拦截器创建"""
        assert "orchestrator" in interceptor.valid_services
        assert "gateway" in interceptor.valid_services
