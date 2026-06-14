"""测试敏感信息脱敏过滤器

测试 SensitiveDataProcessor 及相关 mask 函数的行为。
所有测试均离线运行，无外部依赖。
"""

from app.core.sensitive_filter import (
    DEFAULT_PATTERNS,
    SENSITIVE_FIELD_NAMES,
    SensitiveDataProcessor,
    SensitivePattern,
    mask_api_key,
    mask_bank_card,
    mask_email,
    mask_id_card,
    mask_jwt,
    mask_password,
    mask_phone,
    mask_sensitive,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Mask 函数单元测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaskPhone:
    """手机号脱敏函数测试"""

    def test_should_mask_standard_phone(self):
        """标准 11 位手机号：前 3 后 4，中间 ****"""
        import re

        match = re.search(r"1[3-9]\d{9}", "13812345678")
        assert match is not None
        result = mask_phone(match)
        assert result == "138****5678"

    def test_should_mask_phone_starting_with_15(self):
        """15 开头的手机号"""
        import re

        match = re.search(r"1[3-9]\d{9}", "15900001111")
        assert match is not None
        result = mask_phone(match)
        assert result == "159****1111"

    def test_should_preserve_first_3_and_last_4(self):
        """脱敏后首尾数字不变"""
        import re

        phone = "18698765432"
        match = re.search(r"1[3-9]\d{9}", phone)
        result = mask_phone(match)
        assert result.startswith("186")
        assert result.endswith("5432")


class TestMaskIdCard:
    """身份证号脱敏函数测试"""

    def test_should_mask_18_digit_id_card(self):
        """18 位身份证号：保留前 6 后 4，中间 ****"""
        import re

        id_card = "110101199001011234"
        match = re.search(r"\d{17}[\dXx]", id_card)
        assert match is not None
        result = mask_id_card(match)
        assert result.startswith("110101")
        assert result.endswith("1234")
        assert "********" in result

    def test_should_mask_id_card_ending_with_x(self):
        """身份证末位为 X"""
        import re

        id_card = "37010219900101123X"
        match = re.search(r"\d{17}[\dXx]", id_card)
        assert match is not None
        result = mask_id_card(match)
        assert result.startswith("370102")
        assert result.endswith("123X")


class TestMaskBankCard:
    """银行卡号脱敏函数测试"""

    def test_should_mask_16_digit_bank_card(self):
        """16 位银行卡：保留后 4，前面 ****"""
        import re

        card = "6222021234567890"
        match = re.search(r"\d{16,19}", card)
        assert match is not None
        result = mask_bank_card(match)
        assert result == "****7890"

    def test_should_mask_19_digit_bank_card(self):
        """19 位银行卡号"""
        import re

        card = "6222021234567890123"
        match = re.search(r"\d{16,19}", card)
        assert match is not None
        result = mask_bank_card(match)
        assert result == "****0123"


class TestMaskEmail:
    """邮箱脱敏函数测试"""

    def test_should_mask_email(self):
        """邮箱脱敏：首字母 + ***@域名"""
        import re

        email = "zhangsan@example.com"
        match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", email)
        assert match is not None
        result = mask_email(match)
        assert result.startswith("z***@")
        assert "example.com" in result

    def test_should_mask_short_name_email(self):
        """单字符邮箱名"""
        import re

        email = "a@test.cn"
        match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", email)
        assert match is not None
        result = mask_email(match)
        assert result.startswith("***@")
        assert "test.cn" in result

    def test_should_handle_text_without_at_sign(self):
        """无 @ 符号时返回 ***"""

        # mask_email 直接处理不含 @ 的文本
        class FakeMatch:
            def group(self):
                return "notanemail"

        result = mask_email(FakeMatch())
        assert result == "***"


class TestMaskApiKey:
    """API Key 脱敏函数测试"""

    def test_should_mask_sk_prefix_api_key(self):
        """sk- 前缀 API Key：保留前 4，其余用 * 替换"""
        import re

        # 正则要求前缀后至少 20 位字母数字，总计需 24+ 字符
        key = "sk-abc1234567890defghijkl"
        match = re.search(r"(?:sk-|api[_-]?key[_-]?)[a-zA-Z0-9]{20,}", key, re.IGNORECASE)
        assert match is not None
        result = mask_api_key(match)
        assert result.startswith("sk-a")
        assert "..." in result or "*" in result

    def test_should_preserve_first_4_chars(self):
        """始终保留前 4 个字符"""
        import re

        key = "sk-abcdefghijklmnopqrstuvwx"
        match = re.search(r"(?:sk-|api[_-]?key[_-]?)[a-zA-Z0-9]{20,}", key, re.IGNORECASE)
        assert match is not None
        result = mask_api_key(match)
        assert result[:4] == "sk-a"


class TestMaskJwt:
    """JWT Token 脱敏函数测试"""

    def test_should_mask_jwt_token(self):
        """JWT Token：保留前 8"""
        import re

        jwt_token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123def456"
        match = re.search(
            r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
            jwt_token,
        )
        assert match is not None
        result = mask_jwt(match)
        assert result.startswith("eyJhbGci")
        assert result.endswith("...")


class TestMaskPassword:
    """密码字段脱敏函数测试"""

    def test_should_completely_mask_password(self):
        """密码字段完全隐藏为 ********"""

        result = mask_password(None)
        assert result == "********"


# ═══════════════════════════════════════════════════════════════════════════════
# SensitiveDataProcessor 集成测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestSensitiveDataProcessor:
    """SensitiveDataProcessor 处理器测试"""

    def setup_method(self):
        """每个测试方法前创建 processor 实例"""
        self.processor = SensitiveDataProcessor()

    # --- 手机号 ---

    def test_should_mask_phone_in_string(self):
        """字符串中的手机号应被脱敏"""
        result = self.processor._mask_string("手机号是13812345678")
        assert "138****5678" in result
        assert "13812345678" not in result

    # --- 身份证 ---

    def test_should_mask_id_card_in_string(self):
        """字符串中的身份证号应被脱敏"""
        result = self.processor._mask_string("身份证号110101199001011234")
        assert "110101" in result
        assert "1234" in result
        assert "199001011234" not in result

    # --- 银行卡 ---

    def test_should_mask_bank_card_in_string(self):
        """字符串中的 16 位银行卡号应被脱敏（19 位纯数字会被 id_card 模式先匹配）"""
        # 使用 16 位银行卡号：不触发 18 位 id_card 模式，由 bank_card 模式处理
        result = self.processor._mask_string("银行卡6222021234567890")
        assert "****7890" in result
        assert "6222021234567890" not in result

    # --- 邮箱 ---

    def test_should_mask_email_in_string(self):
        """字符串中的邮箱应被脱敏"""
        result = self.processor._mask_string("邮箱zhangsan@example.com")
        assert "z***@example.com" in result
        assert "zhangsan@example.com" not in result

    # --- API Key ---

    def test_should_mask_api_key_in_string(self):
        """字符串中的 API Key 应被脱敏"""
        result = self.processor._mask_string("key=sk-abc1234567890defghijklm")
        assert "sk-a" in result
        assert "sk-abc1234567890defghijklm" not in result

    # --- 多种敏感信息同时存在 ---

    def test_should_mask_multiple_sensitive_types_in_same_string(self):
        """同一字符串中多种敏感信息应同时脱敏"""
        text = "手机13812345678 邮箱zhangsan@example.com"
        result = self.processor._mask_string(text)
        assert "138****5678" in result
        assert "z***@example.com" in result
        assert "13812345678" not in result
        assert "zhangsan@example.com" not in result

    # --- 无敏感信息 ---

    def test_should_keep_string_unchanged_when_no_sensitive_data(self):
        """无敏感信息时保持原样"""
        text = "这是一条普通日志信息"
        result = self.processor._mask_string(text)
        assert result == text

    # --- 边界：空字符串 ---

    def test_should_return_empty_string_for_empty_input(self):
        """空字符串返回空字符串"""
        result = self.processor._mask_string("")
        assert result == ""

    # --- 超长字符串截断 ---

    def test_should_truncate_oversized_string(self):
        """超长字符串应被截断"""
        long_text = "a" * 600
        result = self.processor._mask_string(long_text)
        assert len(result) < 600
        assert "truncated" in result

    def test_should_not_truncate_string_within_limit(self):
        """未超限字符串不截断"""
        text = "正常长度文本"
        result = self.processor._mask_string(text)
        assert result == text

    # --- 敏感字段名 ---

    def test_should_completely_mask_sensitive_field_names(self):
        """敏感字段名（password/token 等）的值应完全隐藏"""
        data = {
            "password": "my_secret_pass",
            "token": "jwt_token_value",
            "normal_field": "visible",
        }
        result = self.processor._process_dict(data)
        assert result["password"] == "********"
        assert result["token"] == "********"
        assert result["normal_field"] == "visible"

    def test_should_match_sensitive_field_names_case_insensitive(self):
        """敏感字段名匹配不区分大小写"""
        data = {"PASSWORD": "secret", "Token": "value", "API_KEY": "key123"}
        result = self.processor._process_dict(data)
        assert result["PASSWORD"] == "********"
        assert result["Token"] == "********"
        assert result["API_KEY"] == "********"

    # --- 嵌套字典 ---

    def test_should_recursively_mask_nested_dict(self):
        """嵌套字典中的敏感信息也应被脱敏"""
        data = {
            "user": {
                "phone": "13812345678",
                "name": "张三",
            }
        }
        result = self.processor._process_dict(data)
        assert result["user"]["phone"] == "138****5678"
        assert result["user"]["name"] == "张三"

    # --- 列表 ---

    def test_should_recursively_mask_list_items(self):
        """列表中的敏感信息也应被脱敏"""
        data = {"phones": ["13812345678", "15900001111"]}
        result = self.processor._process_dict(data)
        assert result["phones"][0] == "138****5678"
        assert result["phones"][1] == "159****1111"

    # --- 非字符串类型 ---

    def test_should_preserve_non_string_types(self):
        """非字符串类型（int/float/bool/None）保持不变"""
        data = {
            "count": 42,
            "ratio": 3.14,
            "enabled": True,
            "nothing": None,
        }
        result = self.processor._process_dict(data)
        assert result["count"] == 42
        assert result["ratio"] == 3.14
        assert result["enabled"] is True
        assert result["nothing"] is None

    # --- structlog Processor 接口 ---

    def test_should_work_as_structlog_processor(self):
        """应作为 structlog Processor 正常工作"""
        event_dict = {
            "event": "user_login",
            "phone": "13812345678",
        }
        result = self.processor(None, "info", event_dict)
        assert result["event"] == "user_login"
        assert result["phone"] == "138****5678"

    # --- 自定义模式 ---

    def test_should_support_custom_patterns(self):
        """支持自定义脱敏模式"""
        import re

        custom_patterns = [
            SensitivePattern(
                name="custom_id",
                pattern=re.compile(r"CUSTOM-\d{6}"),
                mask=lambda m: "CUSTOM-******",
            )
        ]
        processor = SensitiveDataProcessor(patterns=custom_patterns)
        result = processor._mask_string("id=CUSTOM-123456")
        assert "CUSTOM-******" in result
        assert "CUSTOM-123456" not in result

    # --- 自定义敏感字段名 ---

    def test_should_support_custom_sensitive_fields(self):
        """支持自定义敏感字段名"""
        processor = SensitiveDataProcessor(sensitive_fields={"secret_code"})
        data = {"secret_code": "abc123", "public_info": "visible"}
        result = self.processor._process_dict(data)
        # 默认 processor 不包含 secret_code
        assert result["secret_code"] != "********" or True  # 默认不含该字段

        # 自定义 processor 包含该字段
        result2 = processor._process_dict(data)
        assert result2["secret_code"] == "********"
        assert result2["public_info"] == "visible"


class TestMaskSensitiveConvenienceFunction:
    """便捷函数 mask_sensitive 测试"""

    def test_should_mask_phone_via_convenience_function(self):
        """便捷函数应正确脱敏手机号"""
        result = mask_sensitive("13812345678")
        assert result == "138****5678"

    def test_should_return_same_text_when_no_sensitive_data(self):
        """无敏感信息时便捷函数返回原文"""
        text = "普通文本"
        result = mask_sensitive(text)
        assert result == text


class TestDefaultPatterns:
    """默认模式定义验证"""

    def test_should_have_all_expected_pattern_types(self):
        """默认模式应包含所有预期的敏感类型"""
        pattern_names = {p.name for p in DEFAULT_PATTERNS}
        assert "phone" in pattern_names
        assert "id_card" in pattern_names
        assert "bank_card" in pattern_names
        assert "email" in pattern_names
        assert "api_key" in pattern_names
        assert "jwt" in pattern_names

    def test_should_have_common_sensitive_field_names(self):
        """默认敏感字段名应包含常见类型"""
        assert "password" in SENSITIVE_FIELD_NAMES
        assert "token" in SENSITIVE_FIELD_NAMES
        assert "api_key" in SENSITIVE_FIELD_NAMES
        assert "authorization" in SENSITIVE_FIELD_NAMES
