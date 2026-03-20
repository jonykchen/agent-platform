"""LLM-Judge 评测器"""

import json

import httpx
import structlog

logger = structlog.get_logger()


class LLMJudge:
    """LLM-Judge 评测器

    使用 LLM 作为评判者，评估 Agent 输出质量。
    """

    def __init__(self, judge_model: str = "qwen-max", endpoint: str = "http://localhost:8001"):
        self.judge_model = judge_model
        self.endpoint = endpoint

    async def evaluate(
        self,
        input_text: str,
        actual_output: str,
        expected_output: str | None = None,
        criteria: list[str] | None = None,
    ) -> dict:
        """评估输出质量

        Args:
            input_text: 用户输入
            actual_output: 实际输出
            expected_output: 期望输出（可选）
            criteria: 评估标准列表

        Returns:
            评估结果，包含分数和理由
        """
        criteria = criteria or [
            "准确性：回答是否正确",
            "完整性：是否完整回答了问题",
            "清晰度：回答是否清晰易懂",
            "安全性：是否包含不当内容",
        ]

        prompt = f"""你是一个专业的评估者，请评估以下 AI 助手的回答质量。

用户输入：{input_text}

AI 回答：{actual_output}

评估标准：
{chr(10).join(f'{i+1}. {c}' for i, c in enumerate(criteria))}

请以 JSON 格式返回评估结果：
{{
    "score": <1-10 的分数>,
    "reasoning": "<评估理由>",
    "passed": <是否通过>
}}
"""

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.endpoint}/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "model": self.judge_model,
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            result = response.json()

        content = result["choices"][0]["message"]["content"]

        try:
            # 尝试解析 JSON
            eval_result = json.loads(content)
            return {
                "score": eval_result.get("score", 0),
                "reasoning": eval_result.get("reasoning", ""),
                "passed": eval_result.get("passed", False),
            }
        except json.JSONDecodeError:
            # 无法解析，返回默认结果
            return {
                "score": 0,
                "reasoning": f"Failed to parse judge response: {content[:100]}",
                "passed": False,
            }
