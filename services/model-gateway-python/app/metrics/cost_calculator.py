"""成本计算器

计算模型调用成本。
"""

import structlog

logger = structlog.get_logger()


# 模型定价（美元/千 token）
MODEL_PRICING = {
    # Qwen 系列
    "qwen-max": {"input": 0.02, "output": 0.06},
    "qwen-plus": {"input": 0.004, "output": 0.012},
    "qwen-turbo": {"input": 0.002, "output": 0.006},
    "qwen-long": {"input": 0.004, "output": 0.012},

    # GLM 系列
    "glm-4": {"input": 0.014, "output": 0.014},
    "glm-4-plus": {"input": 0.05, "output": 0.05},
    "glm-4-flash": {"input": 0.001, "output": 0.001},

    # Kimi
    "kimi": {"input": 0.012, "output": 0.012},
    "moonshot-v1-8k": {"input": 0.012, "output": 0.012},

    # DeepSeek
    "deepseek-chat": {"input": 0.001, "output": 0.002},
    "deepseek-coder": {"input": 0.001, "output": 0.002},

    # 默认
    "default": {"input": 0.01, "output": 0.03},
}


class CostCalculator:
    """成本计算器"""

    def __init__(self, pricing: dict | None = None):
        self.pricing = pricing or MODEL_PRICING

    def calculate(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """计算成本

        Args:
            model: 模型名称
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数

        Returns:
            成本（美元）
        """
        # 获取定价
        pricing = self.pricing.get(model, self.pricing["default"])

        # 计算成本
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]

        total_cost = input_cost + output_cost

        logger.debug(
            "Cost calculated",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=total_cost,
        )

        return total_cost

    def estimate(
        self,
        model: str,
        estimated_tokens: int,
        input_ratio: float = 0.6,
    ) -> float:
        """预估成本

        Args:
            model: 模型名称
            estimated_tokens: 预估总 token
            input_ratio: 输入占比

        Returns:
            预估成本（美元）
        """
        prompt_tokens = int(estimated_tokens * input_ratio)
        completion_tokens = estimated_tokens - prompt_tokens

        return self.calculate(model, prompt_tokens, completion_tokens)

    def get_pricing(self, model: str) -> dict:
        """获取模型定价"""
        return self.pricing.get(model, self.pricing["default"])

    def list_pricing(self) -> dict:
        """列出所有定价"""
        return self.pricing


# 全局实例
_calculator = None


def get_cost_calculator() -> CostCalculator:
    """获取成本计算器实例"""
    global _calculator
    if _calculator is None:
        _calculator = CostCalculator()
    return _calculator


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """便捷函数：计算成本"""
    return get_cost_calculator().calculate(model, prompt_tokens, completion_tokens)