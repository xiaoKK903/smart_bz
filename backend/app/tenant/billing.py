"""计费引擎模块"""

from typing import Dict, List, Optional
import time


class BillingEngine:
    """计费引擎"""

    def __init__(self):
        self.usage_records = {}  #  usage_records[tenant_id][session_id] = {tokens, cost, timestamp}
        self.pricing = {
            "deepseek-chat": {
                "input": 0.0001,  # 每千token价格
                "output": 0.0002
            },
            "deepseek-v3": {
                "input": 0.0002,
                "output": 0.0004
            },
            "gpt-3.5-turbo": {
                "input": 0.00015,
                "output": 0.0002
            },
            "gpt-4o": {
                "input": 0.0005,
                "output": 0.0015
            }
        }

    def record_usage(self, tenant_id: str, session_id: str, model: str, input_tokens: int, output_tokens: int):
        """
        记录使用量
        
        Args:
            tenant_id: 租户ID
            session_id: 会话ID
            model: 模型名称
            input_tokens: 输入token数
            output_tokens: 输出token数
        """
        if tenant_id not in self.usage_records:
            self.usage_records[tenant_id] = {}
        
        if session_id not in self.usage_records[tenant_id]:
            self.usage_records[tenant_id][session_id] = {
                "tokens": {
                    "input": 0,
                    "output": 0,
                    "total": 0
                },
                "cost": 0.0,
                "timestamp": time.time()
            }
        
        # 更新使用量
        record = self.usage_records[tenant_id][session_id]
        record["tokens"]["input"] += input_tokens
        record["tokens"]["output"] += output_tokens
        record["tokens"]["total"] += input_tokens + output_tokens
        
        # 计算成本
        cost = self._calculate_cost(model, input_tokens, output_tokens)
        record["cost"] += cost

    def get_tenant_usage(self, tenant_id: str, start_time: Optional[float] = None, end_time: Optional[float] = None) -> Dict:
        """
        获取租户使用情况
        
        Args:
            tenant_id: 租户ID
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            Dict: 使用情况
        """
        if tenant_id not in self.usage_records:
            return {
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_cost": 0.0,
                "session_count": 0
            }
        
        total_tokens = 0
        input_tokens = 0
        output_tokens = 0
        total_cost = 0.0
        session_count = 0
        
        for session_id, record in self.usage_records[tenant_id].items():
            timestamp = record["timestamp"]
            if start_time and timestamp < start_time:
                continue
            if end_time and timestamp > end_time:
                continue
            
            total_tokens += record["tokens"]["total"]
            input_tokens += record["tokens"]["input"]
            output_tokens += record["tokens"]["output"]
            total_cost += record["cost"]
            session_count += 1
        
        return {
            "total_tokens": total_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_cost": total_cost,
            "session_count": session_count
        }

    def get_session_usage(self, tenant_id: str, session_id: str) -> Optional[Dict]:
        """
        获取会话使用情况
        
        Args:
            tenant_id: 租户ID
            session_id: 会话ID
            
        Returns:
            Optional[Dict]: 使用情况
        """
        if tenant_id in self.usage_records and session_id in self.usage_records[tenant_id]:
            return self.usage_records[tenant_id][session_id]
        return None

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        计算成本
        
        Args:
            model: 模型名称
            input_tokens: 输入token数
            output_tokens: 输出token数
            
        Returns:
            float: 成本
        """
        # 找到模型的定价
        model_pricing = None
        for model_key, pricing in self.pricing.items():
            if model.startswith(model_key):
                model_pricing = pricing
                break
        
        if not model_pricing:
            # 默认使用deepseek-chat的定价
            model_pricing = self.pricing["deepseek-chat"]
        
        # 计算成本
        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]
        
        return input_cost + output_cost

    def cleanup_old_records(self, days: int = 30):
        """
        清理旧记录
        
        Args:
            days: 保留天数
        """
        cutoff_time = time.time() - (days * 24 * 3600)
        
        for tenant_id in list(self.usage_records.keys()):
            for session_id in list(self.usage_records[tenant_id].keys()):
                if self.usage_records[tenant_id][session_id]["timestamp"] < cutoff_time:
                    del self.usage_records[tenant_id][session_id]
            
            # 如果租户没有记录了，删除租户
            if not self.usage_records[tenant_id]:
                del self.usage_records[tenant_id]


# 全局计费引擎实例
billing = BillingEngine()