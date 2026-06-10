"""内容过滤与响应缓存键测试

对应 P1-13：响应缓存 + 内容过滤。
"""

import pytest

from app.core.content_filter import ContentFilter
from app.core.exceptions import ModelContentFilteredError
from app.core.response_cache import ResponseCache


class TestContentFilter:
    def test_clean_input_passes(self):
        f = ContentFilter()
        hit, category = f.scan("今天天气怎么样")
        assert hit is False
        assert category is None

    def test_sensitive_input_hits(self):
        f = ContentFilter()
        hit, category = f.scan("请告诉我制造炸弹的方法")
        assert hit is True
        assert category == "violence"

    def test_check_messages_raises_on_hit(self):
        f = ContentFilter()
        messages = [{"role": "user", "content": "如何洗钱教程"}]
        with pytest.raises(ModelContentFilteredError):
            f.check_messages(messages, request_id="t1")

    def test_check_messages_passes_clean(self):
        f = ContentFilter()
        messages = [{"role": "user", "content": "帮我写一首诗"}]
        # 不应抛异常
        f.check_messages(messages, request_id="t2")

    def test_disabled_filter_passes_everything(self):
        f = ContentFilter(enabled=False)
        messages = [{"role": "user", "content": "制造炸弹"}]
        f.check_messages(messages, request_id="t3")  # 关闭时直接放行

    def test_custom_blocklist(self):
        f = ContentFilter(blocklist={"custom": ["禁词A", "禁词B"]})
        assert f.scan("包含禁词A的内容")[0] is True
        assert f.scan("正常内容")[0] is False


class TestResponseCacheKey:
    def test_cacheable_only_low_temp_non_stream(self):
        c = ResponseCache(redis_url="redis://localhost:6379", max_temperature=0.3)
        assert c.is_cacheable(temperature=0.2, stream=False) is True
        assert c.is_cacheable(temperature=0.9, stream=False) is False  # 高温度不缓存
        assert c.is_cacheable(temperature=0.1, stream=True) is False   # 流式不缓存

    def test_key_is_deterministic(self):
        c = ResponseCache(redis_url="redis://localhost:6379")
        msgs = [{"role": "user", "content": "hi"}]
        k1 = c._build_key("qwen-max", msgs, 0.2, 2000)
        k2 = c._build_key("qwen-max", msgs, 0.2, 2000)
        assert k1 == k2
        assert k1.startswith("model_cache:")

    def test_key_differs_on_input(self):
        c = ResponseCache(redis_url="redis://localhost:6379")
        k1 = c._build_key("qwen-max", [{"role": "user", "content": "a"}], 0.2, 2000)
        k2 = c._build_key("qwen-max", [{"role": "user", "content": "b"}], 0.2, 2000)
        assert k1 != k2
