"""意图识别引擎 — 规则优先 + LLM 兜底"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class IntentResult:
    """意图识别结果"""
    intent: str
    confidence: float
    domain: str          # "bazi" | "ecommerce" | "general"
    method: str          # "rule" | "llm"


# ────────── 规则定义 ──────────

# 八字域
BAZI_RULES: Dict[str, List[str]] = {
    "bazi_reading": [
        r"八字", r"命理", r"命盘", r"排盘", r"四柱", r"天干", r"地支",
        r"日主", r"五行", r"喜用神", r"忌神", r"格局", r"十神",
        r"出生.*分析", r"帮我.*算", r"测.*命",
    ],
    "fortune_query": [
        r"运势", r"大运", r"流年", r"流月", r"今年.*运", r"明年.*运",
        r"本月.*运", r"运气", r"走运",
    ],
    "career_advice": [
        r"事业", r"工作", r"职业", r"跳槽", r"晋升", r"职场",
        r"适合.*做什么", r"工作运", r"求职",
    ],
    "relationship_advice": [
        r"感情", r"婚姻", r"恋爱", r"爱情", r"配偶", r"桃花",
        r"姻缘", r"另一半", r"对象",
    ],
    "health_advice": [
        r"健康", r"身体", r"养生", r"健康运", r"疾病",
    ],
}

# 电商域
ECOMMERCE_RULES: Dict[str, List[str]] = {
    "order_status": [
        r"订单.*状态", r"我的订单", r"订单号", r"查.*订单",
    ],
    "logistics_query": [
        r"物流", r"快递", r"到哪了", r"发货", r"运单", r"什么时候到",
        r"几天到", r"到了吗", r"tracking",
    ],
    "refund_request": [
        r"退款", r"退钱", r"不想要了", r"申请退",
    ],
    "return_request": [
        r"退货", r"退回去", r"寄回",
    ],
    "refund_status": [
        r"退款.*进度", r"退款.*到账", r"退了吗", r"钱.*退.*了吗",
    ],
    "product_consult": [
        r"商品.*咨询", r"有没有.*卖", r"多少钱", r"规格", r"尺码",
    ],
    "complaint": [
        r"投诉", r"315", r"消协", r"工商", r"曝光", r"起诉",
        r"差评", r"太差了", r"骗子",
    ],
    "human_agent": [
        r"转人工", r"人工客服", r"真人", r"找个人",
    ],
}

# 通用意图
GENERAL_RULES: Dict[str, List[str]] = {
    "greeting": [
        r"^你好$", r"^您好", r"^嗨$", r"^hello", r"^hi$", r"^hey",
        r"^早上好", r"^下午好", r"^晚上好",
    ],
    "farewell": [
        r"^再见", r"^拜拜", r"^bye", r"^下次见",
    ],
}

# intent → domain 映射
INTENT_DOMAIN_MAP: Dict[str, str] = {}
for intent in BAZI_RULES:
    INTENT_DOMAIN_MAP[intent] = "bazi"
for intent in ECOMMERCE_RULES:
    INTENT_DOMAIN_MAP[intent] = "ecommerce"
for intent in GENERAL_RULES:
    INTENT_DOMAIN_MAP[intent] = "general"
INTENT_DOMAIN_MAP["general_query"] = "general"


class IntentClassifier:
    """混合意图识别器"""

    def __init__(self):
        # 合并所有规则
        self.all_rules: Dict[str, List[re.Pattern]] = {}
        for rules_dict in [BAZI_RULES, ECOMMERCE_RULES, GENERAL_RULES]:
            for intent, patterns in rules_dict.items():
                self.all_rules[intent] = [re.compile(p, re.IGNORECASE) for p in patterns]

    def classify(self, text: str, active_domain: Optional[str] = None) -> IntentResult:
        """
        识别意图

        Args:
            text: 用户输入
            active_domain: 当前活跃的领域（用于上下文消歧）

        Returns:
            IntentResult
        """
        if not text or not text.strip():
            return IntentResult("general_query", 0.5, "general", "rule")

        text_clean = text.strip()

        # ── 第一步：规则匹配 ──
        result = self._rule_match(text_clean, active_domain)
        if result:
            return result

        # ── 第二步：LLM 兜底（这里用简单启发式代替，避免每轮都调LLM）──
        result = self._heuristic_fallback(text_clean, active_domain)
        return result

    def _rule_match(self, text: str, active_domain: Optional[str] = None) -> Optional[IntentResult]:
        """规则匹配"""
        matches = []

        for intent, patterns in self.all_rules.items():
            for pattern in patterns:
                if pattern.search(text):
                    domain = INTENT_DOMAIN_MAP.get(intent, "general")
                    # 如果有活跃域，同域意图加分
                    bonus = 0.1 if (active_domain and domain == active_domain) else 0.0
                    matches.append(IntentResult(intent, 0.9 + bonus, domain, "rule"))
                    break

        if not matches:
            return None

        # 如果有多个匹配，优先业务意图（非 greeting/farewell/general_query）
        business = [m for m in matches if m.intent not in ("greeting", "farewell", "general_query")]
        if business:
            # 优先活跃域
            if active_domain:
                same_domain = [m for m in business if m.domain == active_domain]
                if same_domain:
                    return same_domain[0]
            return business[0]

        return matches[0]

    def _heuristic_fallback(self, text: str, active_domain: Optional[str] = None) -> IntentResult:
        """启发式兜底（不调LLM，基于关键词模糊匹配）"""
        # 如果当前在八字域，倾向归到 general_query + bazi
        if active_domain == "bazi":
            # 看看是否像在问命理问题
            bazi_hints = ["我", "适合", "能不能", "应该", "什么时候", "今年", "明年", "方位", "颜色", "数字"]
            if any(h in text for h in bazi_hints):
                return IntentResult("general_query", 0.6, "bazi", "rule")

        if active_domain == "ecommerce":
            return IntentResult("general_query", 0.6, "ecommerce", "rule")

        # 完全无线索
        return IntentResult("general_query", 0.5, "general", "rule")

    def get_domain_for_intent(self, intent: str) -> str:
        """获取意图对应的域"""
        return INTENT_DOMAIN_MAP.get(intent, "general")


# 全局实例
intent_classifier = IntentClassifier()
