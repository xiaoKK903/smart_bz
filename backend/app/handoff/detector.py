"""转人工检测模块"""

from typing import Dict, List, Optional


class HandoffDetector:
    """转人工检测器"""

    def __init__(self):
        # 转人工关键词
        self.handoff_keywords = [
            "转人工", "人工客服", "真人", "找个人", "人工服务",
            "投诉", "315", "消协", "工商", "曝光", "起诉"
        ]
        
        # 情绪关键词（负面）
        self.negative_keywords = [
            "生气", "愤怒", "不满", "失望", "投诉", "差评",
            "退款", "退货", "欺骗", "垃圾", "差劲", "没用"
        ]

    def detect_handoff(self, session: Dict) -> Dict:
        """
        检测是否需要转人工
        
        Args:
            session: 会话信息
            
        Returns:
            Dict: 检测结果
        """
        # 1. 检测显式请求
        if self._detect_explicit_request(session):
            return {
                "should_handoff": True,
                "reason": "explicit_request",
                "confidence": 1.0
            }
        
        # 2. 检测低置信度
        if self._detect_low_confidence(session):
            return {
                "should_handoff": True,
                "reason": "low_confidence",
                "confidence": 0.8
            }
        
        # 3. 检测负面情绪
        if self._detect_negative_sentiment(session):
            return {
                "should_handoff": True,
                "reason": "negative_sentiment",
                "confidence": 0.7
            }
        
        # 4. 检测死循环
        if self._detect_loop(session):
            return {
                "should_handoff": True,
                "reason": "loop_detected",
                "confidence": 0.6
            }
        
        return {
            "should_handoff": False,
            "reason": "no_handoff_needed",
            "confidence": 1.0
        }

    def _detect_explicit_request(self, session: Dict) -> bool:
        """
        检测显式转人工请求
        
        Args:
            session: 会话信息
            
        Returns:
            bool: 是否检测到
        """
        recent_messages = session.get("messages", [])
        for msg in recent_messages[-5:]:  # 检查最近5条消息
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                for keyword in self.handoff_keywords:
                    if keyword in content:
                        return True
        return False

    def _detect_low_confidence(self, session: Dict) -> bool:
        """
        检测连续低置信度
        
        Args:
            session: 会话信息
            
        Returns:
            bool: 是否检测到
        """
        recent_intents = session.get("intent_history", [])
        if len(recent_intents) < 3:
            return False
        
        # 检查最近3轮的置信度
        low_confidence_count = 0
        for intent_info in recent_intents[-3:]:
            confidence = intent_info.get("confidence", 1.0)
            if confidence < 0.4:
                low_confidence_count += 1
        
        return low_confidence_count >= 3

    def _detect_negative_sentiment(self, session: Dict) -> bool:
        """
        检测负面情绪
        
        Args:
            session: 会话信息
            
        Returns:
            bool: 是否检测到
        """
        recent_messages = session.get("messages", [])
        negative_count = 0
        
        for msg in recent_messages[-3:]:  # 检查最近3条消息
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                for keyword in self.negative_keywords:
                    if keyword in content:
                        negative_count += 1
                        break
        
        return negative_count >= 2

    def _detect_loop(self, session: Dict) -> bool:
        """
        检测对话死循环
        
        Args:
            session: 会话信息
            
        Returns:
            bool: 是否检测到
        """
        messages = session.get("messages", [])
        if len(messages) < 8:  # 至少8轮对话
            return False
        
        # 检查最近的消息是否重复
        recent_contents = []
        for msg in messages[-8:]:
            recent_contents.append(msg.get("content", "").lower())
        
        # 检查是否有重复模式
        for i in range(len(recent_contents) - 3):
            if recent_contents[i] == recent_contents[i+2] and recent_contents[i+1] == recent_contents[i+3]:
                return True
        
        return False


# 全局检测器实例
detector = HandoffDetector()