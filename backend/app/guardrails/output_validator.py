"""输出验证器模块"""

from typing import Dict, Optional
import re


class OutputValidator:
    """输出验证器"""

    def __init__(self):
        # 禁用话术
        self.banned_phrases = [
            "我无法回答这个问题",
            "根据相关法律法规",
            "你可以尝试",
            "建议你",
            "抱歉，我不能",
            "我不知道"
        ]
        
        # 过度承诺短语
        self.over_promises = [
            "保证",
            "一定",
            "绝对",
            "完全",
            "100%",
            "肯定",
            "必须"
        ]
        
        # 信息泄露模式
        self.leak_patterns = [
            r"API_KEY",
            r"token",
            r"password",
            r"secret",
            r"1[3-9]\d{9}",  # 手机号
            r"[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]"  # 身份证号
        ]

    def validate_output(self, text: str) -> Dict:
        """
        验证输出
        
        Args:
            text: 输出文本
            
        Returns:
            Dict: 验证结果
        """
        result = {
            "original": text,
            "validated": text,
            "is_safe": True,
            "warnings": []
        }
        
        # 检测禁用话术
        banned = self._detect_banned(text)
        if banned:
            result["is_safe"] = False
            result["warnings"].append(f"包含禁用话术: {', '.join(banned)}")
        
        # 检测过度承诺
        promises = self._detect_over_promises(text)
        if promises:
            result["validated"] = self._replace_over_promises(text)
            result["warnings"].append(f"包含过度承诺: {', '.join(promises)}")
        
        # 检测信息泄露
        leaks = self._detect_leaks(text)
        if leaks:
            result["validated"] = self._mask_leaks(text)
            result["warnings"].append("可能包含信息泄露")
        
        return result

    def _detect_banned(self, text: str) -> list:
        """
        检测禁用话术
        
        Args:
            text: 输出文本
            
        Returns:
            list: 检测到的禁用话术
        """
        detected = []
        for phrase in self.banned_phrases:
            if phrase in text:
                detected.append(phrase)
        return detected

    def _detect_over_promises(self, text: str) -> list:
        """
        检测过度承诺
        
        Args:
            text: 输出文本
            
        Returns:
            list: 检测到的过度承诺短语
        """
        detected = []
        for phrase in self.over_promises:
            if phrase in text:
                detected.append(phrase)
        return detected

    def _detect_leaks(self, text: str) -> list:
        """
        检测信息泄露
        
        Args:
            text: 输出文本
            
        Returns:
            list: 检测到的泄露模式
        """
        detected = []
        for pattern in self.leak_patterns:
            if re.search(pattern, text):
                detected.append(pattern)
        return detected

    def _replace_over_promises(self, text: str) -> str:
        """
        替换过度承诺
        
        Args:
            text: 输出文本
            
        Returns:
            str: 替换后的文本
        """
        replacements = {
            "保证": "建议",
            "一定": "可能",
            "绝对": "相对",
            "完全": "比较",
            "100%": "大部分",
            "肯定": "可能",
            "必须": "建议"
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text

    def _mask_leaks(self, text: str) -> str:
        """
        脱敏信息泄露
        
        Args:
            text: 输出文本
            
        Returns:
            str: 脱敏后的文本
        """
        # 手机号脱敏
        text = re.sub(r"1([3-9]\d{2})\d{4}(\d{4})", r"1\1****\2", text)
        
        # 身份证号脱敏
        text = re.sub(r"([1-9]\d{5})(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}([\dXx])", r"\1**********\6", text)
        
        # API密钥脱敏
        text = re.sub(r"(API_KEY|api_key|ApiKey)\s*[:=]\s*['\"]([^'\"]+)['\"]", r"\1: '***'", text)
        
        # Token脱敏
        text = re.sub(r"(token|Token)\s*[:=]\s*['\"]([^'\"]+)['\"]", r"\1: '***'", text)
        
        return text


# 全局输出验证器实例
output_validator = OutputValidator()