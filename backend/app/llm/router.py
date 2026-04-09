"""LLM 路由模块

根据意图复杂度和租户配置，选择合适的模型和 provider。
支持 chat messages 格式和简单 prompt 格式。
"""

from typing import Optional, Dict, Any, List

from app.config import settings
from app.llm.providers import deepseek, openai
from app.llm.fallback import fallback_manager


class LMRouter:
    """LLM 路由器"""

    def __init__(self):
        self.providers = {
            "deepseek": deepseek,
            "openai": openai,
        }

        # 意图复杂度映射
        self.intent_complexity = {
            # 简单意图
            "order_status": "simple",
            "logistics_query": "simple",
            "refund_status": "simple",
            "greeting": "simple",
            "farewell": "simple",
            "coupon_query": "simple",
            # 中等复杂度
            "product_consult": "medium",
            "fortune_query": "medium",
            "general_query": "medium",
            # 复杂意图
            "complaint": "complex",
            "refund_request": "complex",
            "return_request": "complex",
            "exchange_request": "complex",
            "bazi_reading": "complex",
            "relationship_advice": "complex",
            "career_advice": "complex",
            "health_advice": "complex",
        }

        # 模型映射
        self.model_mapping = {
            "simple": "deepseek-chat",
            "medium": "deepseek-chat",
            "complex": "deepseek-chat",
        }

    def _get_model_by_intent(self, intent: str) -> str:
        """根据意图获取合适的模型"""
        complexity = self.intent_complexity.get(intent, "medium")
        return self.model_mapping.get(complexity, "deepseek-chat")

    def _get_provider(self, model: str):
        """根据模型名称获取对应的 provider 模块"""
        if model.startswith("gpt"):
            return self.providers.get("openai")
        # 默认使用 deepseek
        return self.providers.get("deepseek")

    async def generate(
        self,
        tenant_id: str,
        prompt: str,
        model: str = None,
        temperature: float = 0.3,
        max_tokens: int = 800,
        intent: str = None,
        system_prompt: str = None,
    ) -> Dict[str, Any]:
        """
        生成文本（兼容旧接口）

        Args:
            tenant_id: 租户 ID
            prompt: 用户消息 / 提示词
            model: 模型名称（不传则根据意图自动选择）
            temperature: 温度
            max_tokens: 最大 token 数
            intent: 意图名称
            system_prompt: 系统提示词

        Returns:
            Dict: {"text": str, "model_used": str, "status": str}
        """
        if not model:
            model = self._get_model_by_intent(intent) if intent else settings.default_model

        provider = self._get_provider(model)

        # 尝试主模型
        try:
            if system_prompt and hasattr(provider, 'generate'):
                result = await provider.generate(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                )
            else:
                result = await provider.generate(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            fallback_manager.record_success(model)
            return {"text": result, "model_used": model, "status": "success"}

        except Exception as e:
            print(f"[LLM Router] 主模型 {model} 生成失败: {e}")
            fallback_manager.record_failure(model)

        # 尝试 fallback 链
        for fb in fallback_manager.get_fallback_chain(model):
            fb_model = fb["model"]
            fb_provider = self._get_provider(fb_model)
            try:
                if system_prompt and hasattr(fb_provider, 'generate'):
                    result = await fb_provider.generate(
                        prompt=prompt,
                        model=fb_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        system_prompt=system_prompt,
                    )
                else:
                    result = await fb_provider.generate(
                        prompt=prompt,
                        model=fb_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                fallback_manager.record_success(fb_model)
                return {"text": result, "model_used": fb_model, "status": "fallback"}

            except Exception as e2:
                print(f"[LLM Router] fallback 模型 {fb_model} 失败: {e2}")
                fallback_manager.record_failure(fb_model)

        # 所有模型都失败 → 兜底回复
        domain = None
        if intent:
            # 从意图推断领域
            bazi_intents = {"bazi_reading", "fortune_query", "relationship_advice",
                            "career_advice", "health_advice"}
            if intent in bazi_intents:
                domain = "bazi"
            else:
                domain = "ecommerce"

        error_type = fallback_manager.classify_error(Exception("all models failed"))
        fallback_text = fallback_manager.get_fallback_response(domain=domain, error_type=error_type)

        return {"text": fallback_text, "model_used": None, "status": "error"}

    async def chat(
        self,
        tenant_id: str,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.3,
        max_tokens: int = 800,
        intent: str = None,
    ) -> Dict[str, Any]:
        """
        使用完整 messages 格式调用 LLM

        Args:
            tenant_id: 租户 ID
            messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
            model: 模型名称
            temperature: 温度
            max_tokens: 最大 token 数
            intent: 意图名称

        Returns:
            Dict: {"text": str, "model_used": str, "status": str}
        """
        if not model:
            model = self._get_model_by_intent(intent) if intent else settings.default_model

        provider = self._get_provider(model)

        # 尝试主模型
        try:
            if hasattr(provider, 'chat'):
                result = await provider.chat(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                # provider 不支持 chat，降级为 generate
                user_msg = messages[-1]["content"] if messages else ""
                sys_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
                result = await provider.generate(
                    prompt=user_msg,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=sys_msg,
                )
            fallback_manager.record_success(model)
            return {"text": result, "model_used": model, "status": "success"}

        except Exception as e:
            print(f"[LLM Router] chat 调用 {model} 失败: {e}")
            fallback_manager.record_failure(model)

        # fallback
        for fb in fallback_manager.get_fallback_chain(model):
            fb_model = fb["model"]
            fb_provider = self._get_provider(fb_model)
            try:
                if hasattr(fb_provider, 'chat'):
                    result = await fb_provider.chat(
                        messages=messages,
                        model=fb_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                else:
                    user_msg = messages[-1]["content"] if messages else ""
                    sys_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
                    result = await fb_provider.generate(
                        prompt=user_msg,
                        model=fb_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        system_prompt=sys_msg,
                    )
                fallback_manager.record_success(fb_model)
                return {"text": result, "model_used": fb_model, "status": "fallback"}

            except Exception as e2:
                print(f"[LLM Router] chat fallback {fb_model} 失败: {e2}")
                fallback_manager.record_failure(fb_model)

        # 兜底
        fallback_text = fallback_manager.get_fallback_response()
        return {"text": fallback_text, "model_used": None, "status": "error"}


# 全局 LLM 路由器实例
router = LMRouter()
