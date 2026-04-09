"""槽位管理器 — 从用户消息中提取槽位，跟踪填充状态"""

import re
from typing import Dict, List, Optional, Tuple


# ════════════════════════════════════════════
#  中文数字 / 时辰 解析工具（从旧项目迁移）
# ════════════════════════════════════════════

_CN_DIGIT = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

_SHICHEN_NAMES = [
    "子时", "丑时", "寅时", "卯时", "辰时", "巳时",
    "午时", "未时", "申时", "酉时", "戌时", "亥时",
]


def _cn_to_int(s: str) -> Optional[int]:
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s.startswith("初"):
        r = _cn_to_int(s[1:])
        return r if r and 1 <= r <= 10 else None
    if s.startswith("廿"):
        if len(s) == 1:
            return 20
        r = _cn_to_int(s[1:])
        return 20 + r if r and 1 <= r <= 9 else None
    if s.startswith("卅"):
        if len(s) == 1:
            return 30
        r = _cn_to_int(s[1:])
        return 30 + r if r and r <= 1 else None
    if "十" in s:
        parts = s.split("十")
        tens = _CN_DIGIT.get(parts[0], 1) if parts[0] else 1
        ones = _CN_DIGIT.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    if s in _CN_DIGIT:
        return _CN_DIGIT[s]
    return None


def _hour_to_shichen(hour: int) -> str:
    idx = ((hour + 1) % 24) // 2
    return _SHICHEN_NAMES[idx]


# ════════════════════════════════════════════
#  各种槽位类型的提取函数
# ════════════════════════════════════════════

def _extract_gender(text: str) -> Optional[str]:
    female = [r"(?:我是|性别[是为：:]*\s*)(?:女|女性|女生|女孩|女士)",
              r"(?:的|出生的)\s*(?:女生|女孩|女性|女的|女士)"]
    male = [r"(?:我是|性别[是为：:]*\s*)(?:男|男性|男生|男孩|先生)",
            r"(?:的|出生的)\s*(?:男生|男孩|男性|男的)"]
    for p in female:
        if re.search(p, text):
            return "女"
    for p in male:
        if re.search(p, text):
            return "男"
    if len(text) <= 5:
        if re.match(r"^[男]$", text):
            return "男"
        if re.match(r"^[女]$", text):
            return "女"
    return None


def _extract_full_date(text: str) -> Dict[str, str]:
    result = {}
    m = re.search(
        r"(\d{4}|[一二三四五六七八九零〇]{4})\s*年\s*"
        r"(\d{1,2}|[一二三四五六七八九十]+)\s*月\s*"
        r"(\d{1,2}|[一二三四五六七八九十初廿卅]+)\s*[日号]?", text)
    if m:
        y = m.group(1)
        if not y.isdigit():
            y = "".join(str(_CN_DIGIT.get(c, c)) for c in y)
        result["birth_year"] = y
        mo = _cn_to_int(m.group(2))
        if mo and 1 <= mo <= 12:
            result["birth_month"] = str(mo)
        d = _cn_to_int(m.group(3))
        if d and 1 <= d <= 31:
            result["birth_day"] = str(d)
        return result
    m = re.search(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", text)
    if m:
        result["birth_year"] = m.group(1)
        mo = int(m.group(2))
        if 1 <= mo <= 12:
            result["birth_month"] = str(mo)
        d = int(m.group(3))
        if 1 <= d <= 31:
            result["birth_day"] = str(d)
    return result


def _extract_year(text: str) -> Optional[str]:
    m = re.search(r"(?:^|[^\d])(\d{4})\s*年", text)
    if m:
        y = int(m.group(1))
        if 1900 <= y <= 2030:
            return str(y)
    m = re.search(r"(?:^|[^\d])(\d{2})\s*年", text)
    if m:
        y = int(m.group(1))
        full = 1900 + y if y >= 20 else 2000 + y
        if 1900 <= full <= 2030:
            return str(full)
    m = re.search(r"(?:^|[^\d])(19\d{2}|20[0-2]\d)(?:[^\d]|$)", text)
    if m:
        return m.group(1)
    return None


def _extract_month(text: str) -> Optional[str]:
    m = re.search(r"(?:^|[^\d])(\d{1,2})\s*月", text)
    if m:
        mo = int(m.group(1))
        if 1 <= mo <= 12:
            return str(mo)
    m = re.search(r"([一二三四五六七八九十]+)\s*月", text)
    if m:
        mo = _cn_to_int(m.group(1))
        if mo and 1 <= mo <= 12:
            return str(mo)
    lunar = {"正月": "1", "腊月": "12", "冬月": "11"}
    for name, val in lunar.items():
        if name in text:
            return val
    return None


def _extract_day(text: str) -> Optional[str]:
    m = re.search(r"(?:^|[^\d])(\d{1,2})\s*[日号]", text)
    if m:
        d = int(m.group(1))
        if 1 <= d <= 31:
            return str(d)
    m = re.search(r"([初廿卅]?[一二三四五六七八九十]{1,2})\s*[日号]", text)
    if m:
        d = _cn_to_int(m.group(1))
        if d and 1 <= d <= 31:
            return str(d)
    return None


def _extract_hour(text: str) -> Optional[str]:
    m = re.search(r"([子丑寅卯辰巳午未申酉戌亥])\s*时", text)
    if m:
        return m.group(1) + "时"
    m = re.search(r"(\d{1,2})\s*[点时]", text)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            prefix = text[:m.start()]
            if re.search(r"(?:下午|晚上|傍晚|夜里)", prefix[-10:]):
                if h < 12:
                    h += 12
            return _hour_to_shichen(h)
    m = re.search(r"(\d{1,2}):(\d{2})", text)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return _hour_to_shichen(h)
    return None


def _extract_order_id(text: str) -> Optional[str]:
    """提取订单号"""
    m = re.search(r"[A-Za-z0-9]{10,20}", text)
    return m.group(0) if m else None


def _extract_phone(text: str) -> Optional[str]:
    """提取手机号"""
    m = re.search(r"1[3-9]\d{9}", text)
    return m.group(0) if m else None


# ════════════════════════════════════════════
#  意图 → 所需槽位定义
# ════════════════════════════════════════════

# 八字域槽位
BAZI_REQUIRED_SLOTS = {
    "bazi_reading": ["birth_year", "birth_month", "birth_day", "birth_hour", "gender"],
    "fortune_query": ["birth_year", "birth_month", "birth_day", "birth_hour", "gender"],
    "career_advice": ["birth_year", "birth_month", "birth_day", "birth_hour", "gender"],
    "relationship_advice": ["birth_year", "birth_month", "birth_day", "birth_hour", "gender"],
    "health_advice": ["birth_year", "birth_month", "birth_day", "birth_hour", "gender"],
}

# 电商域槽位
ECOMMERCE_REQUIRED_SLOTS = {
    "order_status": ["order_id"],
    "logistics_query": ["order_id"],
    "refund_request": ["order_id", "refund_reason"],
    "return_request": ["order_id", "return_reason"],
    "refund_status": ["order_id"],
}

# 槽位中文标签 + 追问提示
SLOT_LABELS = {
    "birth_year":    ("出生年份", "请问您出生于哪一年？"),
    "birth_month":   ("出生月份", "请问您出生于几月份？"),
    "birth_day":     ("出生日期", "请问您出生于几号？"),
    "birth_hour":    ("出生时辰", "请问您出生于什么时辰（或几点）？"),
    "gender":        ("性别", "请问您的性别是？"),
    "order_id":      ("订单号", "请提供您的订单号。"),
    "refund_reason": ("退款原因", "请问退款原因是什么？"),
    "return_reason": ("退货原因", "请问退货原因是什么？"),
    "phone":         ("手机号", "请提供下单时的手机号。"),
}


class SlotManager:
    """槽位管理器"""

    def get_required_slots(self, intent: str) -> List[str]:
        """获取意图所需的槽位列表"""
        if intent in BAZI_REQUIRED_SLOTS:
            return BAZI_REQUIRED_SLOTS[intent]
        if intent in ECOMMERCE_REQUIRED_SLOTS:
            return ECOMMERCE_REQUIRED_SLOTS[intent]
        return []

    def extract_slots(self, text: str, intent: str) -> Dict[str, str]:
        """
        从用户消息中提取槽位值

        Args:
            text: 用户消息
            intent: 当前意图

        Returns:
            提取到的槽位 {key: value}
        """
        result = {}

        if intent in BAZI_REQUIRED_SLOTS:
            result = self._extract_bazi_slots(text)
        elif intent in ECOMMERCE_REQUIRED_SLOTS:
            result = self._extract_ecommerce_slots(text)

        return result

    def get_missing_slots(self, intent: str, filled: Dict[str, str]) -> List[str]:
        """获取还缺失的槽位"""
        required = self.get_required_slots(intent)
        return [s for s in required if s not in filled or not filled[s]]

    def build_slot_prompt(self, filled: Dict[str, str], missing: List[str]) -> str:
        """生成槽位追问提示（注入到 system prompt 中）"""
        lines = []

        if filled:
            lines.append("【已收集信息】")
            for k, v in filled.items():
                label = SLOT_LABELS.get(k, (k, ""))[0]
                lines.append(f"  - {label}: {v}")

        if missing:
            lines.append("【还需要以下信息】")
            for k in missing:
                label = SLOT_LABELS.get(k, (k, ""))[0]
                lines.append(f"  - {label}")
            lines.append("")
            lines.append(
                "请自然地向用户询问上述缺失信息。语气亲切自然，"
                "不要像填表一样逐项追问。如果用户已提供了某些信息，直接确认即可。"
            )
        else:
            lines.append("【所需信息已收集完毕，可以进行分析】")

        return "\n".join(lines)

    def _extract_bazi_slots(self, text: str) -> Dict[str, str]:
        """提取八字域槽位"""
        result = {}
        gender = _extract_gender(text)
        if gender:
            result["gender"] = gender

        date_result = _extract_full_date(text)
        result.update(date_result)

        if "birth_year" not in result:
            year = _extract_year(text)
            if year:
                result["birth_year"] = year
        if "birth_month" not in result:
            month = _extract_month(text)
            if month:
                result["birth_month"] = month
        if "birth_day" not in result:
            day = _extract_day(text)
            if day:
                result["birth_day"] = day
        if "birth_hour" not in result:
            hour = _extract_hour(text)
            if hour:
                result["birth_hour"] = hour

        return result

    def _extract_ecommerce_slots(self, text: str) -> Dict[str, str]:
        """提取电商域槽位"""
        result = {}
        order_id = _extract_order_id(text)
        if order_id:
            result["order_id"] = order_id
        phone = _extract_phone(text)
        if phone:
            result["phone"] = phone
        # refund_reason / return_reason 比较自由，由 LLM 从对话中提取
        return result


# 全局实例
slot_manager = SlotManager()
