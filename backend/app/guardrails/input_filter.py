"""输入过滤器模块"""

from typing import Dict, Optional
import re


class InputFilter:
    """输入过滤器"""

    def __init__(self, sensitive_words=None):
        # 敏感词列表
        if sensitive_words:
            self.sensitive_words = sensitive_words
        else:
            self.sensitive_words = [
                # 政治敏感词
                "敏感词1", "敏感词2",
                # 违法违规词
                "赌博", "色情", "毒品",
                # 辱骂词
                "傻逼", "垃圾", "废物"
            ]
        
        # Prompt注入模式
        self.injection_patterns = [
            r"ignore previous instructions",
            r"system prompt",
            r"你是一个",
            r"让我告诉你",
            r"忘记之前的",
            r"忽略之前的",
            r"重新开始"
        ]

    def filter_input(self, text: str) -> Dict:
        """
        过滤输入
        
        Args:
            text: 输入文本
            
        Returns:
            Dict: 过滤结果
        """
        result = {
            "original": text,
            "filtered": text,
            "is_safe": True,
            "warnings": []
        }
        
        # 检测敏感词
        sensitive = self._detect_sensitive(text)
        if sensitive:
            result["is_safe"] = False
            result["warnings"].append(f"包含敏感词: {', '.join(sensitive)}")
        
        # 检测Prompt注入
        injection = self._detect_injection(text)
        if injection:
            result["is_safe"] = False
            result["warnings"].append(f"可能的Prompt注入: {', '.join(injection)}")
        
        # 检测个人信息
        pii = self._detect_pii(text)
        if pii:
            result["filtered"] = self._mask_pii(text)
            result["warnings"].append(f"包含个人信息: {', '.join(pii.keys())}")
        
        return result

    def _detect_sensitive(self, text: str) -> list:
        """
        检测敏感词
        
        Args:
            text: 输入文本
            
        Returns:
            list: 检测到的敏感词
        """
        detected = []
        for word in self.sensitive_words:
            if word in text:
                detected.append(word)
        return detected

    def _detect_injection(self, text: str) -> list:
        """
        检测Prompt注入
        
        Args:
            text: 输入文本
            
        Returns:
            list: 检测到的注入模式
        """
        detected = []
        text_lower = text.lower()
        for pattern in self.injection_patterns:
            if re.search(pattern, text_lower):
                detected.append(pattern)
        return detected

    def _detect_pii(self, text: str) -> Dict:
        """
        检测个人信息
        
        Args:
            text: 输入文本
            
        Returns:
            Dict: 检测到的个人信息
        """
        pii = {}
        
        # 手机号
        phone_pattern = r"1[3-9]\d{9}"
        phones = re.findall(phone_pattern, text)
        if phones:
            pii["phone"] = phones
        
        # 身份证号
        id_pattern = r"[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]"
        ids = re.findall(id_pattern, text)
        if ids:
            pii["id_card"] = ids
        
        # 邮箱
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        emails = re.findall(email_pattern, text)
        if emails:
            pii["email"] = emails
        
        return pii

    def _mask_pii(self, text: str) -> str:
        """
        脱敏个人信息
        
        Args:
            text: 输入文本
            
        Returns:
            str: 脱敏后的文本
        """
        # 手机号脱敏
        text = re.sub(r"1([3-9]\d{2})\d{4}(\d{4})", r"1\1****\2", text)
        
        # 身份证号脱敏
        text = re.sub(r"([1-9]\d{5})(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}([\dXx])", r"\1**********\6", text)
        
        # 邮箱脱敏
        text = re.sub(r"([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", r"***@\2", text)
        
        return text


# 全局输入过滤器实例
input_filter = InputFilter()