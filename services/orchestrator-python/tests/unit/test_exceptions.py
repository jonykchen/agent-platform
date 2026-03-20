"""测试异常类"""

import pytest

from app.core.exceptions import (
    BasePlatformException,
    InvalidRequestError,
    MaxStepsExceededError,
    ToolNotFoundError,
    AllProvidersDownError,
)


def test_base_exception():
    """测试基础异常"""
    e = BasePlatformException("Test error", code="ERR_TEST", user_message="测试错误")
    assert e.message == "Test error"
    assert e.code == "ERR_TEST"
    assert e.user_message == "测试错误"
    assert e.to_dict()["error"] == "ERR_TEST"


def test_invalid_request_error():
    """测试无效请求错误"""
    e = InvalidRequestError("Invalid parameter", details={"field": "name"})
    assert e.code == "ERR_INVALID_REQUEST"
    assert e.details["field"] == "name"


def test_max_steps_exceeded_error():
    """测试最大步骤超限错误"""
    e = MaxStepsExceededError(10)
    assert e.code == "ERR_AGENT_MAX_STEPS_EXCEEDED"
    assert e.details["max_steps"] == 10


def test_tool_not_found_error():
    """测试工具不存在错误"""
    e = ToolNotFoundError("query_order")
    assert e.code == "ERR_AGENT_TOOL_NOT_FOUND"
    assert "query_order" in e.message


def test_all_providers_down_error():
    """测试所有提供商不可用错误"""
    e = AllProvidersDownError()
    assert e.code == "ERR_MODEL_ALL_PROVIDERS_DOWN"
    assert "AI 服务" in e.user_message
