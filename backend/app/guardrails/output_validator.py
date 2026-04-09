"""输出安全校验"""


class OutputValidator:
    """校验 LLM 输出，拦截不当内容"""

    FORBIDDEN_PHRASES = [
        "这不是我们的问题",
        "你自己去看",
        "我是AI",
        "作为一个大语言模型",
    ]

    def validate(self, response: str, intent: str) -> tuple[str, list[str]]:
        """返回 (cleaned_response, warnings)"""
        warnings = []

        # 1. 禁用话术检测
        for phrase in self.FORBIDDEN_PHRASES:
            if phrase in response:
                warnings.append(f"forbidden_phrase:{phrase}")

        # 2. 承诺检测（退款场景不能说"立即到账"）
        if intent in ("refund_request", "return_request"):
            if "立即到账" in response or "马上退" in response:
                warnings.append("over_promise:refund_timing")

        # 3. 信息泄露检测（不能暴露内部系统信息）
        leak_keywords = ["数据库", "API", "token", "密钥", "内部系统"]
        for kw in leak_keywords:
            if kw in response:
                warnings.append(f"info_leak:{kw}")

        return response, warnings
