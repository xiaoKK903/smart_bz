"""全局配置"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ─── 应用 ───
    app_name: str = "智能客服平台"
    debug: bool = False

    # ─── 数据库 ───
    database_url: str = "postgresql+asyncpg://localhost:5432/smartcs"
    redis_url: str = "redis://localhost:6379/0"

    # ─── LLM ───
    deepseek_api_key: str = "sk-e4a2167e3d384e5a9266bdc6ec9b43da"
    deepseek_base_url: str = "https://api.deepseek.com"
    openai_api_key: Optional[str] = None
    default_model: str = "deepseek-chat"
    default_temperature: float = 0.3
    default_max_tokens: int = 800

    # ─── 向量数据库 ───
    chroma_persist_dir: str = "./data/chroma"

    # ─── 外部服务 ───
    order_api_base: Optional[str] = None
    order_api_token: Optional[str] = None
    logistics_api_base: Optional[str] = None
    product_api_base: Optional[str] = None

    # ─── 安全 ───
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
