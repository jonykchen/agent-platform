"""测试配置"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_request_headers():
    """Mock 请求头"""
    return {
        "X-Request-ID": "test-request-001",
        "X-Tenant-ID": "test-tenant-001",
        "X-User-ID": "test-user-001",
    }
