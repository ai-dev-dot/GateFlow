from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 必需从 .env 读取，不设默认值——缺配置时启动失败而非静默用错数据库/密钥
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    ENCRYPTION_KEY: str  # 上游 API Key 加密，Fernet 格式
    HMAC_SECRET: str  # 客户端 API Key 哈希，至少 32 字节随机串

    JWT_EXPIRE_DAYS: int = 7
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
