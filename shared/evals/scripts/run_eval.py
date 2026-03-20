"""评测脚本 - 运行 Gold Set 评测"""

import asyncio
import json
from pathlib import Path

import httpx
import structlog

logger = structlog.get_logger()


class EvalRunner:
    """评测运行器"""

    def __init__(self, endpoint: str, gold_set_path: Path):
        self.endpoint = endpoint
        self.gold_set_path = gold_set_path
        self.results = []

    def load_gold_set(self) -> list[dict]:
        """加载 Gold Set"""
        cases = []
        for file in self.gold_set_path.glob("*.jsonl"):
            with open(file) as f:
                for line in f:
                    if line.strip():
                        cases.append(json.loads(line))
        return cases

    async def run_case(self, case: dict) -> dict:
        """运行单个评测用例"""
        case_id = case["id"]
        input_text = case["input"]
        expected = case["expected_output"]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.endpoint}/api/v1/chat/completions",
                    json={"message": input_text},
                )
                response.raise_for_status()
                result = response.json()

            # 评估结果
            passed = self.evaluate(result, expected)

            return {
                "case_id": case_id,
                "passed": passed,
                "actual": result,
                "expected": expected,
            }

        except Exception as e:
            return {
                "case_id": case_id,
                "passed": False,
                "error": str(e),
            }

    def evaluate(self, actual: dict, expected: dict) -> bool:
        """评估结果是否符合预期"""
        # 检查包含关键词
        if "contains" in expected:
            response = actual.get("response", "").lower()
            for keyword in expected["contains"]:
                if keyword.lower() not in response:
                    return False

        # 检查工具调用
        if "tool_calls" in expected:
            actual_tools = [t.get("tool_name") for t in actual.get("tool_calls", [])]
            for expected_tool in expected["tool_calls"]:
                if expected_tool not in actual_tools:
                    return False

        return True

    async def run_all(self) -> dict:
        """运行所有评测用例"""
        cases = self.load_gold_set()
        logger.info("Loaded eval cases", count=len(cases))

        results = await asyncio.gather(*[self.run_case(c) for c in cases])

        passed = sum(1 for r in results if r["passed"])
        total = len(results)

        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0,
            "results": results,
        }


async def main():
    runner = EvalRunner(
        endpoint="http://localhost:8080",
        gold_set_path=Path("shared/evals/gold-set"),
    )

    report = await runner.run_all()

    print(f"\n评测报告:")
    print(f"  总数: {report['total']}")
    print(f"  通过: {report['passed']}")
    print(f"  失败: {report['failed']}")
    print(f"  通过率: {report['pass_rate']:.1%}")

    # 保存报告
    with open("shared/evals/reports/eval_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(main())
