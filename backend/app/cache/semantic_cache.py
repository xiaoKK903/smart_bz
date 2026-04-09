"""语义缓存 - 相似问题命中缓存，跳过 LLM 调用"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CacheEntry:
    question: str
    answer: str
    intent: str
    embedding: list[float]
    hit_count: int = 0


class SemanticCache:
    """
    基于向量相似度的语义缓存：
    - 新问题先算 embedding，在缓存中找相似度 > 阈值的
    - 命中 → 直接返回缓存答案，省一次 LLM 调用
    - 未命中 → 走正常流程，结果写入缓存
    """

    def __init__(self, similarity_threshold: float = 0.95, max_size: int = 10000):
        self.threshold = similarity_threshold
        self.max_size = max_size
        self._cache: list[CacheEntry] = []

    async def get(self, question: str, embedding: list[float]) -> Optional[str]:
        """查缓存，返回答案或 None"""
        for entry in self._cache:
            sim = self._cosine_similarity(embedding, entry.embedding)
            if sim >= self.threshold:
                entry.hit_count += 1
                return entry.answer
        return None

    async def put(self, question: str, answer: str, intent: str, embedding: list[float]):
        """写入缓存"""
        if len(self._cache) >= self.max_size:
            # 淘汰命中最少的
            self._cache.sort(key=lambda e: e.hit_count)
            self._cache.pop(0)
        self._cache.append(CacheEntry(
            question=question, answer=answer, intent=intent, embedding=embedding
        ))

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x ** 2 for x in a) ** 0.5
        norm_b = sum(x ** 2 for x in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0
