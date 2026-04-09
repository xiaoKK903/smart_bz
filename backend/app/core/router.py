"""领域路由器 — 根据意图分发到对应插件"""

from typing import Dict, Optional
from app.domains.base.plugin import BaseDomainPlugin


class DomainRouter:
    """领域路由器"""

    def __init__(self):
        self._plugins: Dict[str, BaseDomainPlugin] = {}
        self._intent_domain: Dict[str, str] = {}

    def register(self, domain: str, plugin: BaseDomainPlugin, intents: list[str]):
        """注册一个领域插件及其处理的意图列表"""
        self._plugins[domain] = plugin
        for intent in intents:
            self._intent_domain[intent] = domain

    def route(self, intent: str, domain_hint: Optional[str] = None) -> Optional[BaseDomainPlugin]:
        """
        根据意图找到对应的插件

        Args:
            intent: 意图名称
            domain_hint: 域提示（来自意图识别）

        Returns:
            对应的插件实例，找不到则返回 None
        """
        # 优先用 intent → domain 映射
        domain = self._intent_domain.get(intent)
        if domain and domain in self._plugins:
            return self._plugins[domain]

        # 再用 domain_hint
        if domain_hint and domain_hint in self._plugins:
            return self._plugins[domain_hint]

        return None

    def get_plugin(self, domain: str) -> Optional[BaseDomainPlugin]:
        """直接按域名获取插件"""
        return self._plugins.get(domain)

    def list_domains(self) -> list[str]:
        return list(self._plugins.keys())


def _build_default_router() -> DomainRouter:
    """构建默认路由器，注册所有可用插件"""
    router = DomainRouter()

    # 注册八字插件
    try:
        from app.domains.bazi.plugin import BaziPlugin
        bazi = BaziPlugin()
        router.register("bazi", bazi, [
            "bazi_reading", "fortune_query", "career_advice",
            "relationship_advice", "health_advice",
        ])
    except Exception as e:
        print(f"[Router] 八字插件加载失败: {e}")

    # 注册电商插件
    try:
        from app.domains.ecommerce.plugin import EcommercePlugin
        ecommerce = EcommercePlugin()
        router.register("ecommerce", ecommerce, [
            "order_status", "logistics_query", "refund_request",
            "return_request", "refund_status", "product_consult",
            "complaint", "human_agent",
        ])
    except Exception as e:
        print(f"[Router] 电商插件加载失败: {e}")

    return router


# 全局实例
domain_router = _build_default_router()
