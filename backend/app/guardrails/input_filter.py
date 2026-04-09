"""输入安全过滤"""

import re
from typing import Optional


class InputFilter:
    """防 Prompt 注入 + 敏感词过滤"""

    INJECTION_PATTERNS = [
        r"ignore\s+(previous|above|all)\s+instructions",
        r"你现在是|你不再是|忘记你的",
        r"system\s*prompt|系统提示词",
        r"<\|im_start\|>|<\|im_end\|>",
        r"\[INST\]|\[/INST\]",
    ]

    def __init__(self, sensitive_words: list[str] = None):
        self.sensitive_words = sensitive_words or []
        self._injection_re = re.compile(
            "|".join(self.INJECTION_PATTERNS), re.IGNORECASE
        )

    def check(self, text: str) -> tuple[bool, Optional[str]]:
        """返回 (is_safe, reason)"""
        # 1. Prompt 注入检测
        if self._injection_re.search(text):
            return False, "potential_injection"

        # 2. 敏感词检测
        for word in self.sensitive_words:
            if word in text:
                return False, f"sensitive_word:{word}"

        # 3. 长度限制
        if len(text) > 5000:
            return False, "too_long"

        return True, None
