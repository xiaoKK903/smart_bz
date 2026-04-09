"""八字命理插件"""

import os
import json
import yaml
from typing import Dict, List, Optional

from app.domains.base.plugin import BaseDomainPlugin, Intent, Slot, Tool, Session
from app.domains.bazi.engine import bazi_engine


class BaziPlugin(BaseDomainPlugin):
    """八字命理插件"""

    def __init__(self):
        config = self._load_config()
        super().__init__(config)
        self.knowledge_base = self._load_knowledge()

    def _load_config(self) -> Dict:
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[BaziPlugin] 加载配置失败: {e}")
            return {"name": "八字命理", "intents": []}

    def _load_knowledge(self) -> Dict:
        knowledge = {}
        knowledge_dir = os.path.join(os.path.dirname(__file__), "knowledge")
        if not os.path.isdir(knowledge_dir):
            return knowledge
        for fname in os.listdir(knowledge_dir):
            fpath = os.path.join(knowledge_dir, fname)
            if fname.endswith(".md"):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        knowledge[fname] = f.read()
                except Exception:
                    pass
            elif fname.endswith(".json"):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        knowledge[fname] = json.load(f)
                except Exception:
                    pass
        return knowledge

    # ─── 接口实现 ───

    def get_intents(self) -> List[Intent]:
        intents = []
        for ic in self.config.get("intents", []):
            intents.append(Intent(
                id=ic.get("id", ""),
                name=ic.get("name", ""),
                description=ic.get("description", ""),
            ))
        # 补充默认意图（即使 config.yaml 不全）
        ids = {i.id for i in intents}
        defaults = [
            ("bazi_reading", "八字解读", "根据出生信息进行八字排盘和命理解读"),
            ("fortune_query", "运势查询", "查询特定时间段的运势"),
            ("career_advice", "事业建议", "事业发展方向分析"),
            ("relationship_advice", "感情分析", "感情婚姻方面的分析"),
            ("health_advice", "健康分析", "健康方面的分析"),
        ]
        for d_id, d_name, d_desc in defaults:
            if d_id not in ids:
                intents.append(Intent(id=d_id, name=d_name, description=d_desc))
        return intents

    def get_slots(self, intent: str) -> List[Slot]:
        """八字域所有意图都需要出生信息"""
        return [
            Slot(id="birth_year", type="string", prompt="请问您出生于哪一年？", required=True),
            Slot(id="birth_month", type="string", prompt="请问您出生于几月？", required=True),
            Slot(id="birth_day", type="string", prompt="请问您出生于几号？", required=True),
            Slot(id="birth_hour", type="string", prompt="请问您出生于什么时辰？", required=True),
            Slot(id="gender", type="string", prompt="请问您的性别是？", required=True, values=["男", "女"]),
        ]

    def build_context(self, session: Session) -> str:
        """构建八字领域上下文"""
        parts = []

        # 如果槽位齐全，直接排盘
        slots = session.slots
        if all(k in slots for k in ["birth_year", "birth_month", "birth_day", "birth_hour", "gender"]):
            bazi_result = bazi_engine.calculate(
                slots["birth_year"], slots["birth_month"],
                slots["birth_day"], slots["birth_hour"], slots["gender"]
            )
            if "error" not in bazi_result:
                parts.append("【排盘结果】")
                parts.append(f"八字: {bazi_result['八字']}")
                parts.append(f"日主: {bazi_result['日主']}")
                parts.append(f"身强身弱: {bazi_result['身强身弱']}")
                parts.append(f"五行分布: {bazi_result['五行分布']}")
                parts.append(f"用神: {', '.join(bazi_result['用神'])}")
                parts.append(f"忌神: {', '.join(bazi_result['忌神'])}")
                parts.append(f"格局: {bazi_result['格局']}")
                parts.append("")
                parts.append("【大运】")
                for dy in bazi_result.get("大运", []):
                    parts.append(f"  {dy['年龄段']}: {dy['干支']}({dy['五行']})")
            else:
                parts.append(f"排盘出错: {bazi_result['error']}")
        else:
            filled = {k: v for k, v in slots.items() if v}
            if filled:
                parts.append("【已收集信息】")
                for k, v in filled.items():
                    parts.append(f"  {k}: {v}")

        # 添加知识库上下文
        knowledge_text = self.knowledge_base.get("命理基础.md", "")
        if knowledge_text:
            parts.append(f"\n【知识参考】\n{knowledge_text[:500]}")

        return "\n".join(parts)

    def get_system_prompt(self, intent: str) -> str:
        return """你是一位专业的八字命理师，精通八字排盘、命理解读、运势分析。

## 职责
1. 准确理解用户的问题和需求
2. 基于八字理论和排盘结果进行专业分析
3. 提供详细、准确的解读和建议
4. 保持专业、客观的态度

## 分析要求
- 结合排盘结果分析八字格局、十神关系、用神忌神
- 提供运势分析和发展建议
- 语言通俗易懂，避免过于晦涩的术语
- 保持积极正面的引导

## 注意
- 不做绝对化预测，使用"可能""建议"等表达
- 如信息不足，自然地引导用户补充
- 不涉及封建迷信，从学术和心理学角度分析"""

    def post_process(self, response: str, session: Session) -> str:
        if "运势" in response or "命理" in response or "八字" in response:
            if "温馨提示" not in response:
                response += "\n\n**温馨提示**：命理分析仅供参考，命运掌握在自己手中。"
        return response

    def get_tools(self) -> List[Tool]:
        return []

    def on_session_start(self, session: Session):
        session.set_quick_replies(["八字排盘", "今年运势", "事业分析", "感情分析"])

    def on_session_end(self, session: Session):
        session.save_summary(f"八字咨询 | 意图: {session.current_intent} | 槽位: {session.slots}")
