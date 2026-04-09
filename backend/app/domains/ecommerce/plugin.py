"""电商售后领域插件"""

import os
import yaml
from typing import List, Optional

from app.domains.base.plugin import BaseDomainPlugin, Intent, Slot, Session, Tool


# ─── Mock 数据（替代真实 API） ───

MOCK_ORDERS = {
    "ORD2024001234": {
        "id": "ORD2024001234",
        "status": "shipped",
        "total_amount": 299.00,
        "items": [{"name": "无线蓝牙耳机", "quantity": 1, "price": 299.00}],
        "created_at": "2024-03-15 14:30:00",
        "shipping_address": "北京市朝阳区xxx",
    },
    "ORD2024005678": {
        "id": "ORD2024005678",
        "status": "delivered",
        "total_amount": 158.00,
        "items": [{"name": "保温杯", "quantity": 2, "price": 79.00}],
        "created_at": "2024-03-10 09:15:00",
        "shipping_address": "上海市浦东新区xxx",
    },
}

MOCK_LOGISTICS = {
    "ORD2024001234": {
        "company": "顺丰速运",
        "tracking_no": "SF1234567890",
        "status": "运输中",
        "estimated_delivery": "2024-03-18",
        "tracks": [
            {"time": "2024-03-16 18:00", "content": "已到达 北京转运中心"},
            {"time": "2024-03-16 08:00", "content": "已从 深圳 发出"},
            {"time": "2024-03-15 20:00", "content": "已揽收"},
        ],
    },
}


class EcommercePlugin(BaseDomainPlugin):
    """电商售后领域插件"""

    def __init__(self):
        config = self._load_config()
        super().__init__(config)

    def _load_config(self) -> dict:
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[EcommercePlugin] 加载配置失败: {e}")
            return {"name": "电商售后", "intents": []}

    # ─── 接口实现 ───

    def get_intents(self) -> List[Intent]:
        intents = []
        for ic in self.config.get("intents", []):
            intents.append(Intent(
                id=ic.get("id", ""),
                name=ic.get("name", ""),
                description=ic.get("description", ""),
            ))
        # 补充默认意图
        ids = {i.id for i in intents}
        defaults = [
            ("order_status", "订单查询", "查询订单状态"),
            ("logistics_query", "物流查询", "查询物流进度"),
            ("refund_request", "退款申请", "申请退款"),
            ("return_request", "退货申请", "申请退货"),
            ("product_consult", "商品咨询", "商品相关咨询"),
            ("complaint", "投诉", "用户投诉"),
            ("human_agent", "转人工", "转接人工客服"),
        ]
        for d_id, d_name, d_desc in defaults:
            if d_id not in ids:
                intents.append(Intent(id=d_id, name=d_name, description=d_desc))
        return intents

    def get_slots(self, intent: str) -> List[Slot]:
        if intent in ("order_status", "logistics_query", "refund_status"):
            return [Slot(id="order_id", type="string", prompt="请提供您的订单号。", required=True)]
        if intent == "refund_request":
            return [
                Slot(id="order_id", type="string", prompt="请提供需要退款的订单号。", required=True),
                Slot(id="refund_reason", type="string", prompt="请问退款原因是什么？", required=True),
            ]
        if intent == "return_request":
            return [
                Slot(id="order_id", type="string", prompt="请提供需要退货的订单号。", required=True),
                Slot(id="return_reason", type="string", prompt="请问退货原因是什么？", required=True),
            ]
        return []

    def build_context(self, session: Session) -> str:
        parts = []

        order_id = session.get_slot("order_id")
        if order_id:
            order = MOCK_ORDERS.get(order_id)
            if order:
                status_text = self._status_text(order["status"])
                items_text = ", ".join(
                    f"{i['name']}×{i['quantity']}" for i in order["items"]
                )
                parts.append(
                    f"【订单信息】\n订单号: {order['id']}\n状态: {status_text}\n"
                    f"商品: {items_text}\n金额: ¥{order['total_amount']}\n"
                    f"下单时间: {order['created_at']}"
                )

                logistics = MOCK_LOGISTICS.get(order_id)
                if logistics:
                    tracks = "\n".join(
                        f"  {t['time']} {t['content']}" for t in logistics["tracks"][:3]
                    )
                    parts.append(
                        f"【物流信息】\n快递: {logistics['company']} {logistics['tracking_no']}\n"
                        f"状态: {logistics['status']}\n预计送达: {logistics['estimated_delivery']}\n"
                        f"轨迹:\n{tracks}"
                    )
            else:
                parts.append(f"【订单 {order_id} 未找到】")

        tags = session.user_profile.get("tags", [])
        if tags:
            parts.append(f"【用户标签】{', '.join(tags)}")

        vip = session.user_profile.get("vip_level")
        if vip:
            parts.append(f"【VIP等级】{vip}（请优先处理）")

        return "\n\n".join(parts)

    def get_system_prompt(self, intent: str) -> str:
        base = """你是一位专业的电商售后客服。

## 原则
- 友好、耐心、专业，站在客户角度思考
- 先确认问题，再给方案
- 金额、时效等关键信息必须准确
- 不承诺超出权限的事
- 回复简洁，分步骤说明

## 话术规范
- 禁止说"这不是我们的问题"、"你自己去看"
- 使用"我帮您查看"、"为您处理"、"非常抱歉给您带来不便\""""

        extras = {
            "refund_request": "\n\n## 退款流程\n1. 确认订单号和原因\n2. 查询订单状态\n3. 判断是否符合退款条件\n4. 引导提交申请",
            "complaint": "\n\n## 投诉处理\n1. 认真倾听，表达歉意\n2. 确认问题细节\n3. 给出方案或补偿建议\n4. 升级处理",
            "product_consult": "\n\n## 商品咨询\n1. 基于知识库回答\n2. 不确定的不瞎编\n3. 可适当推荐",
        }
        return base + extras.get(intent, "")

    def post_process(self, response: str, session: Session) -> str:
        intent = session.current_intent
        if intent in ("refund_request", "return_request"):
            order_id = session.get_slot("order_id")
            if order_id and "确认" not in response:
                response += f"\n\n📋 如需提交退款申请，请提供退款原因。"
        if intent == "logistics_query":
            order_id = session.get_slot("order_id")
            logistics = MOCK_LOGISTICS.get(order_id or "")
            if logistics:
                response += f"\n\n📦 运单号: {logistics['tracking_no']}"
        return response

    def get_tools(self) -> List[Tool]:
        return []

    def on_session_start(self, session: Session):
        session.set_quick_replies(["查询订单", "查物流", "申请退款", "商品咨询", "转人工"])

    @staticmethod
    def _status_text(status: str) -> str:
        return {
            "pending": "待付款", "paid": "已付款，待发货",
            "shipped": "已发货，运输中", "delivered": "已签收",
            "completed": "已完成", "cancelled": "已取消",
            "refunding": "退款中", "refunded": "已退款",
        }.get(status, status)
