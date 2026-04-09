"""电商售后领域插件"""

from domains.base import BaseDomainPlugin, Intent, Slot, Session, Tool
from typing import Optional
import httpx


class EcommercePlugin(BaseDomainPlugin):
    """电商售后领域插件"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.order_client = httpx.AsyncClient(
            base_url=config["integrations"]["order_api"]["base_url"],
            headers={"Authorization": config["integrations"]["order_api"]["auth"]},
        )

    # ─────────── 接口实现 ───────────

    def get_intents(self) -> list[Intent]:
        return [Intent.from_yaml(i) for i in self.config["intents"]]

    def get_slots(self, intent: str) -> list[Slot]:
        intent_config = self._find_intent(intent)
        slots = [Slot.from_yaml(s) for s in intent_config.get("required_slots", [])]
        slots += [
            Slot.from_yaml(s, required=False)
            for s in intent_config.get("optional_slots", [])
        ]
        return slots

    def build_context(self, session: Session) -> str:
        context_parts = []

        order_id = session.get_slot("order_id")
        if order_id:
            order_info = self._format_order_info(session.cache.get("order_data"))
            if order_info:
                context_parts.append(f"【订单信息】\n{order_info}")

        logistics = session.cache.get("logistics_data")
        if logistics:
            context_parts.append(f"【物流信息】\n{self._format_logistics(logistics)}")

        user_tags = session.user_profile.get("tags", [])
        if user_tags:
            context_parts.append(f"【用户标签】{', '.join(user_tags)}")

        if session.user_profile.get("vip_level"):
            context_parts.append(
                f"【VIP等级】{session.user_profile['vip_level']}（请优先处理）"
            )

        return "\n\n".join(context_parts)

    def get_system_prompt(self, intent: str) -> str:
        base_prompt = """你是一位专业的电商售后客服。请遵循以下原则：

## 角色
- 友好、耐心、专业
- 始终站在客户角度思考
- 快速定位问题并给出解决方案

## 规则
1. 先确认用户问题，再给方案
2. 涉及退款/退货，必须先查订单状态再处理
3. 金额、时效等关键信息必须准确，不确定时说明
4. 不要承诺超出权限的事情（如"立即退款"）
5. 情绪激动的用户，先安抚再解决
6. 复杂问题超出能力范围，引导转人工

## 话术规范
- 禁止说"这不是我们的问题"
- 禁止说"你自己去看"
- 使用"我帮您查看""为您处理""非常抱歉给您带来不便"
- 回复简洁，避免大段文字，分步骤说明"""

        intent_prompts = {
            "refund_request": """
## 退款处理流程
1. 确认订单号和退款原因
2. 查询订单状态（已发货/未发货/已签收）
3. 根据退换货政策判断是否符合条件
4. 符合 → 引导提交退款申请
5. 不符合 → 解释原因，提供替代方案""",
            "complaint": """
## 投诉处理流程
1. 认真倾听，表达歉意
2. 确认问题细节
3. 给出解决方案或补偿建议
4. 如用户不满意，告知将升级处理
5. 记录投诉内容""",
            "product_consult": """
## 商品咨询
1. 基于知识库中的商品信息回答
2. 不确定的参数不要瞎编
3. 可以适当推荐相关商品
4. 引导用户下单（但不要过度推销）""",
        }

        extra = intent_prompts.get(intent, "")
        return base_prompt + extra

    def post_process(self, response: str, session: Session) -> str:
        intent = session.current_intent

        if intent in ("refund_request", "return_request"):
            order_id = session.get_slot("order_id")
            if order_id and "确认" not in response:
                response += f"\n\n📋 [点击提交退款申请]({self.config['ui'].get('refund_form_url', '#')}?order={order_id})"

        if intent == "logistics_query":
            tracking_no = session.cache.get("tracking_no")
            if tracking_no:
                response += f"\n\n📦 [查看完整物流轨迹](https://www.kuaidi100.com/chaxun?nu={tracking_no})"

        return response

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="query_order",
                description="根据订单号查询订单详情（状态、金额、商品、收货地址）",
                parameters={"order_id": {"type": "string", "description": "订单号"}},
                handler=self._tool_query_order,
            ),
            Tool(
                name="query_logistics",
                description="根据订单号查询物流轨迹",
                parameters={"order_id": {"type": "string", "description": "订单号"}},
                handler=self._tool_query_logistics,
            ),
            Tool(
                name="submit_refund",
                description="提交退款申请",
                parameters={
                    "order_id": {"type": "string", "description": "订单号"},
                    "reason": {"type": "string", "description": "退款原因"},
                    "amount": {
                        "type": "number",
                        "description": "退款金额（可选，默认全额）",
                    },
                },
                handler=self._tool_submit_refund,
                requires_confirmation=True,
            ),
            Tool(
                name="search_product",
                description="搜索商品信息",
                parameters={
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                handler=self._tool_search_product,
            ),
        ]

    # ─────────── 工具实现 ───────────

    async def _tool_query_order(self, order_id: str) -> dict:
        resp = await self.order_client.get(f"/api/orders/{order_id}")
        if resp.status_code == 404:
            return {"error": "未找到该订单，请确认订单号是否正确"}
        data = resp.json()
        return {
            "order_id": data["id"],
            "status": data["status"],
            "status_text": self._status_text(data["status"]),
            "total_amount": data["total_amount"],
            "items": [
                {"name": i["name"], "qty": i["quantity"], "price": i["price"]}
                for i in data["items"]
            ],
            "created_at": data["created_at"],
            "shipping_address": data.get("shipping_address", ""),
        }

    async def _tool_query_logistics(self, order_id: str) -> dict:
        resp = await self.order_client.get(f"/api/orders/{order_id}/logistics")
        if resp.status_code != 200:
            return {"error": "暂无物流信息"}
        data = resp.json()
        return {
            "company": data["company"],
            "tracking_no": data["tracking_no"],
            "status": data["status"],
            "latest": data["tracks"][0] if data["tracks"] else None,
            "estimated_delivery": data.get("estimated_delivery"),
            "tracks": data["tracks"][:5],
        }

    async def _tool_submit_refund(
        self, order_id: str, reason: str, amount: float = None
    ) -> dict:
        payload = {"order_id": order_id, "reason": reason}
        if amount:
            payload["amount"] = amount
        resp = await self.order_client.post("/api/refunds", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "success": True,
                "refund_id": data["refund_id"],
                "estimated_time": "1-3个工作日",
                "message": f"退款申请已提交（单号：{data['refund_id']}），预计1-3个工作日到账。",
            }
        else:
            return {
                "success": False,
                "error": resp.json().get("message", "提交失败，请稍后重试"),
            }

    async def _tool_search_product(self, query: str) -> dict:
        rag_results = await self.rag.search(query, top_k=3)
        return {"products": rag_results}

    # ─────────── 生命周期 ───────────

    def on_session_start(self, session: Session):
        session.set_quick_replies(
            ["查询订单", "查物流", "申请退款", "商品咨询", "转人工"]
        )

    def on_session_end(self, session: Session):
        summary = self._generate_summary(session)
        session.save_summary(summary)

        if session.current_intent == "complaint":
            session.user_profile.setdefault("tags", []).append("有投诉记录")
        if session.current_intent == "refund_request":
            session.user_profile["refund_count"] = (
                session.user_profile.get("refund_count", 0) + 1
            )

    # ─────────── 辅助方法 ───────────

    @staticmethod
    def _status_text(status: str) -> str:
        return {
            "pending": "待付款",
            "paid": "已付款，待发货",
            "shipped": "已发货，运输中",
            "delivered": "已签收",
            "completed": "已完成",
            "cancelled": "已取消",
            "refunding": "退款中",
            "refunded": "已退款",
        }.get(status, status)

    @staticmethod
    def _format_order_info(order: dict) -> str:
        if not order:
            return ""
        items_text = "\n".join(
            f"  - {i['name']} × {i['qty']}  ¥{i['price']}"
            for i in order.get("items", [])
        )
        return f"""订单号：{order['order_id']}
状态：{order['status_text']}
下单时间：{order['created_at']}
商品：
{items_text}
总金额：¥{order['total_amount']}"""

    @staticmethod
    def _format_logistics(logistics: dict) -> str:
        if not logistics:
            return ""
        tracks = "\n".join(
            f"  {t['time']} {t['content']}"
            for t in logistics.get("tracks", [])[:5]
        )
        return f"""快递公司：{logistics['company']}
运单号：{logistics['tracking_no']}
状态：{logistics['status']}
预计送达：{logistics.get('estimated_delivery', '未知')}
最新轨迹：
{tracks}"""

    def _generate_summary(self, session: Session) -> str:
        """生成会话摘要（占位，后续接 LLM）"""
        return f"意图: {session.current_intent}, 槽位: {session.slots}"
