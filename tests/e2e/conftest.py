"""集成测试配置"""

import pytest


@pytest.fixture(scope="session")
def services_ready():
    """检查所有服务是否就绪"""
    import httpx

    services = {
        "gateway": "http://localhost:8080/health",
        "orchestrator": "http://localhost:8000/health",
        "model-gateway": "http://localhost:8001/v1/models",
    }

    for name, url in services.items():
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code not in [200, 404]:
                pytest.skip(f"Service {name} not ready")
        except Exception:
            pytest.skip(f"Service {name} not reachable")


def pytest_configure(config):
    """配置 pytest"""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
