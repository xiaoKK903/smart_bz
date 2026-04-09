"""租户管理模块"""

from typing import Dict, List, Optional
import uuid


class TenantManager:
    """租户管理器"""

    def __init__(self):
        self.tenants = {}  # 租户存储
        self._init_default_tenant()

    def _init_default_tenant(self):
        """
        初始化默认租户
        """
        self.tenants["default"] = {
            "tenant_id": "default",
            "name": "默认租户",
            "plan": "free",
            "domain_plugins": ["ecommerce", "bazi"],
            "llm_config": {
                "default_model": "deepseek-chat",
                "temperature": 0.3,
                "max_tokens": 800
            },
            "branding": {
                "theme_color": "#4A90E2",
                "welcome_message": "您好！我是智能客服助手，有什么可以帮助您的吗？",
                "avatar": ""
            },
            "quota": {
                "monthly_conversations": 100,
                "used_conversations": 0,
                "reset_date": "2024-01-01"
            },
            "webhook_url": ""
        }
        
        # 八字租户
        self.tenants["bazi"] = {
            "tenant_id": "bazi",
            "name": "八字命理",
            "plan": "free",
            "domain_plugins": ["bazi"],
            "llm_config": {
                "default_model": "deepseek-chat",
                "temperature": 0.7,
                "max_tokens": 2000
            },
            "branding": {
                "theme_color": "#8B4513",
                "welcome_message": "您好，我是八字命理师。请告诉我您的出生信息，为您排盘解读。",
                "avatar": ""
            },
            "quota": {
                "monthly_conversations": 100,
                "used_conversations": 0,
                "reset_date": "2024-01-01"
            },
            "webhook_url": ""
        }

    def create_tenant(self, name: str, plan: str = "free") -> Dict:
        """
        创建租户
        
        Args:
            name: 租户名称
            plan: 套餐类型
            
        Returns:
            Dict: 租户信息
        """
        tenant_id = str(uuid.uuid4())
        tenant = {
            "tenant_id": tenant_id,
            "name": name,
            "plan": plan,
            "domain_plugins": ["ecommerce"],
            "llm_config": {
                "default_model": "deepseek-chat",
                "temperature": 0.3,
                "max_tokens": 800
            },
            "branding": {
                "theme_color": "#4A90E2",
                "welcome_message": "您好！我是智能客服助手，有什么可以帮助您的吗？",
                "avatar": ""
            },
            "quota": {
                "monthly_conversations": self._get_plan_quota(plan),
                "used_conversations": 0,
                "reset_date": "2024-01-01"
            },
            "webhook_url": ""
        }
        
        self.tenants[tenant_id] = tenant
        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[Dict]:
        """
        获取租户信息
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            Optional[Dict]: 租户信息
        """
        return self.tenants.get(tenant_id)

    def update_tenant(self, tenant_id: str, updates: Dict) -> Optional[Dict]:
        """
        更新租户信息
        
        Args:
            tenant_id: 租户ID
            updates: 更新内容
            
        Returns:
            Optional[Dict]: 更新后的租户信息
        """
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return None
        
        # 递归更新
        def deep_update(target, source):
            for key, value in source.items():
                if isinstance(value, dict) and key in target:
                    deep_update(target[key], value)
                else:
                    target[key] = value
        
        deep_update(tenant, updates)
        return tenant

    def delete_tenant(self, tenant_id: str) -> bool:
        """
        删除租户
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            bool: 是否成功删除
        """
        if tenant_id == "default":
            return False  # 不能删除默认租户
        
        if tenant_id in self.tenants:
            del self.tenants[tenant_id]
            return True
        
        return False

    def list_tenants(self) -> List[Dict]:
        """
        列出所有租户
        
        Returns:
            List[Dict]: 租户列表
        """
        return list(self.tenants.values())

    def _get_plan_quota(self, plan: str) -> int:
        """
        获取套餐的对话额度
        
        Args:
            plan: 套餐类型
            
        Returns:
            int: 月度对话额度
        """
        quota_map = {
            "free": 100,
            "pro": 5000,
            "enterprise": 999999
        }
        return quota_map.get(plan, 100)

    def check_quota(self, tenant_id: str) -> bool:
        """
        检查租户额度是否充足
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            bool: 额度是否充足
        """
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return False
        
        quota = tenant.get("quota", {})
        used = quota.get("used_conversations", 0)
        total = quota.get("monthly_conversations", 0)
        
        return used < total

    def increment_usage(self, tenant_id: str) -> bool:
        """
        增加租户使用量
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            bool: 是否成功增加
        """
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return False
        
        quota = tenant.get("quota", {})
        quota["used_conversations"] = quota.get("used_conversations", 0) + 1
        return True


# 全局租户管理器实例
manager = TenantManager()