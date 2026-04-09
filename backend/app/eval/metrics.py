"""评测指标体系"""

from dataclasses import dataclass
from enum import Enum


class MetricType(Enum):
    ACCURACY = "accuracy"           # 意图识别准确率
    RESOLUTION_RATE = "resolution"  # 首次解决率 (FCR)
    CSAT = "csat"                   # 客户满意度
    HALLUCINATION = "hallucination" # 幻觉率
    LATENCY = "latency"             # 响应延迟
    COST = "cost"                   # 单次对话成本


@dataclass
class EvalResult:
    metric: MetricType
    score: float
    total: int
    details: dict = None


class MetricsCollector:
    """对话质量评测"""

    async def eval_intent_accuracy(self, test_set: list[dict]) -> EvalResult:
        """意图识别准确率：用标注数据集跑"""
        correct = 0
        for case in test_set:
            predicted = await self._predict_intent(case["input"])
            if predicted == case["expected_intent"]:
                correct += 1
        return EvalResult(
            metric=MetricType.ACCURACY,
            score=correct / len(test_set),
            total=len(test_set),
        )

    async def eval_response_quality(self, session_id: str) -> EvalResult:
        """LLM-as-Judge：用大模型评估回复质量"""
        # 维度：相关性、准确性、完整性、语气
        pass

    async def eval_hallucination(self, response: str, context: str) -> EvalResult:
        """幻觉检测：回复是否超出知识库范围"""
        pass

    async def _predict_intent(self, text: str) -> str:
        pass
