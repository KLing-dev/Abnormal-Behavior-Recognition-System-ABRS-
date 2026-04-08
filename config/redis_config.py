from pydantic_settings import BaseSettings
from typing import Optional


class RedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    decode_responses: bool = True

    class Config:
        env_prefix = "REDIS_"


redis_settings = RedisSettings()
