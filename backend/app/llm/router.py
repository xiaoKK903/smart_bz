"""LLM 路由模块"""

from typing import Optional, Dict, Any

from app.config import settings
from app.llm.providers import deepseek, openai


class LMRouter:
    """LLM 路由器"""

    def __init__(self):
        self.providers = {
            "deepseek": deepseek,
            "openai": openai
        }
        
        # 意图复杂度映射
        self.intent_complexity = {
            # 简单意图
            "order_status": "simple",
            "logistics_query": "simple",
            "refund_status": "simple",
            "product_consult": "medium",
            # 复杂意图
            "complaint": "complex",
            "refund_request": "complex",
            "return_request": "complex",
            "exchange_request": "complex"
        }
        
        # 模型映射
        self.model_mapping = {
            "simple": "deepseek-chat",  # 简单意图用基础模型
            "medium": "deepseek-chat",  # 中等复杂度用标准模型
            "complex": "deepseek-v3"     # 复杂意图用高级模型
        }

    def _get_model_by_intent(self, intent: str) -> str:
        """
        根据意图获取合适的模型
        
        Args:
            intent: 意图名称
            
        Returns:
            str: 模型名称
        """
        complexity = self.intent_complexity.get(intent, "medium")
        return self.model_mapping.get(complexity, "deepseek-chat")

    async def generate(self, tenant_id: str, prompt: str, model: str = None, 
                      temperature: float = 0.3, max_tokens: int = 800, 
                      intent: str = None) -> Dict[str, Any]:
        """
        生成文本
        
        Args:
            tenant_id: 租户 ID
            prompt: 提示词
            model: 模型名称
            temperature: 温度
            max_tokens: 最大 token 数
            intent: 意图名称
        
        Returns:
            Dict: 生成结果，包含文本和使用的模型
        """
        # 如果没有指定模型，根据意图选择
        if not model and intent:
            model = self._get_model_by_intent(intent)
        elif not model:
            model = settings.default_model
        
        # 根据模型选择 provider
        if model.startswith("deepseek"):
            provider = self.providers["deepseek"]
        elif model.startswith("gpt"):
            provider = self.providers["openai"]
        else:
            # 默认使用 deepseek
            provider = self.providers["deepseek"]
        
        # 调用 provider 生成文本
        try:
            result = await provider.generate(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return {
                "text": result,
                "model_used": model,
                "status": "success"
            }
        except Exception as e:
            print(f"[LLM Router] 生成失败: {e}")
            #  fallback 策略
            fallback_models = []
            if provider != self.providers["deepseek"]:
                fallback_models.append(("deepseek-chat", self.providers["deepseek"]))
            
            # 尝试 fallback 模型
            for fallback_model, fallback_provider in fallback_models:
                try:
                    result = await fallback_provider.generate(
                        prompt=prompt,
                        model=fallback_model,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    return {
                        "text": result,
                        "model_used": fallback_model,
                        "status": "fallback"
                    }
                except Exception as e:
                    print(f"[LLM Router] fallback 失败: {e}")
            
            # 所有模型都失败
            return {
                "text": "抱歉，我暂时无法回答您的问题，请稍后再试。",
                "model_used": None,
                "status": "error"
            }


# 全局 LLM 路由器实例
router = LMRouter()