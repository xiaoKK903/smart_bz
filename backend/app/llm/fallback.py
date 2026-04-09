"""LLM 降级策略"""

from typing import List, Dict
import time


# 降级链
FALLBACK_CHAIN = [
    {"provider": "deepseek", "model": "deepseek-chat"},
]

# 兜底回复
FALLBACK_REPLIES = {
    "general": "抱歉，我暂时无法回答您的问题，请稍后再试。",
    "bazi": "抱歉，命理分析服务暂时不可用，请稍后再试。",
    "ecommerce": "抱歉，客服系统暂时繁忙，请稍后再试或联系人工客服。",
}


class FallbackManager:
    """降级管理器 — 跟踪模型健康状态，提供降级链"""

    def __init__(self):
        self._failures: Dict[str, List[float]] = {}  # model → [failure timestamps]
        self._successes: Dict[str, int] = {}

    def record_success(self, model: str):
        """记录成功"""
        self._successes[model] = self._successes.get(model, 0) + 1
        # 成功后清理旧的失败记录
        if model in self._failures:
            self._failures[model] = []

    def record_failure(self, model: str):
        """记录失败"""
        if model not in self._failures:
            self._failures[model] = []
        self._failures[model].append(time.time())
        # 只保留最近 10 条
        self._failures[model] = self._failures[model][-10:]

    def get_fallback_chain(self, failed_model: str = "") -> List[Dict]:
        """获取降级链（排除刚失败的模型）"""
        return [f for f in FALLBACK_CHAIN if f["model"] != failed_model]

    def classify_error(self, error: Exception) -> str:
        """分类错误类型"""
        msg = str(error).lower()
        if "timeout" in msg:
            return "timeout"
        if "rate" in msg or "429" in msg:
            return "rate_limit"
        if "auth" in msg or "401" in msg or "403" in msg:
            return "auth"
        return "unknown"

    def get_fallback_response(self, domain: str = None, error_type: str = None) -> str:
        """获取兜底回复"""
        if domain and domain in FALLBACK_REPLIES:
            return FALLBACK_REPLIES[domain]
        return FALLBACK_REPLIES["general"]


# 全局实例
fallback_manager = FallbackManager()


def get_fallback_reply(domain: str = "general") -> str:
    """快捷函数"""
    return FALLBACK_REPLIES.get(domain, FALLBACK_REPLIES["general"])
