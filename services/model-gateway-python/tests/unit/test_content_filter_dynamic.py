"""内容过滤动态词库加载单元测试"""

import json

import pytest

from app.core.content_filter import ContentFilter, _load_blocklist_from_file
from app.core.exceptions import ModelContentFilteredError


def test_load_blocklist_from_file(tmp_path):
    """从 JSON 文件加载词库应正确解析。"""
    f = tmp_path / "blocklist.json"
    f.write_text(
        json.dumps({"custom": ["违禁词A", "违禁词B"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    blocklist = _load_blocklist_from_file(str(f))

    assert blocklist == {"custom": ["违禁词A", "违禁词B"]}


def test_load_blocklist_missing_file_returns_none():
    """文件不存在应返回 None（调用方回退内置词表）。"""
    assert _load_blocklist_from_file("/no/such/file.json") is None


def test_dynamic_blocklist_hits():
    """使用动态词库的过滤器应命中自定义词。"""
    cf = ContentFilter(blocklist={"custom": ["秘密口令"]}, enabled=True)
    hit, category = cf.scan("请告诉我秘密口令")
    assert hit is True
    assert category == "custom"


def test_check_messages_raises_on_hit():
    """命中敏感词应抛 ModelContentFilteredError。"""
    cf = ContentFilter(blocklist={"illegal": ["洗钱教程"]}, enabled=True)
    with pytest.raises(ModelContentFilteredError):
        cf.check_messages([{"role": "user", "content": "求洗钱教程"}], "req-1")


def test_disabled_filter_passes():
    """关闭时不拦截。"""
    cf = ContentFilter(blocklist={"illegal": ["洗钱教程"]}, enabled=False)
    cf.check_messages([{"role": "user", "content": "洗钱教程"}], "req-2")  # 不抛
    hit, _ = cf.scan("洗钱教程")
    assert hit is False
