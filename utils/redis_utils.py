import redis
from typing import Optional, Any
import json
from config.redis_config import redis_settings


class RedisClient:
    _instance: Optional[redis.Redis] = None

    @classmethod
    def get_instance(cls) -> redis.Redis:
        if cls._instance is None:
            cls._instance = redis.Redis(
                host=redis_settings.host,
                port=redis_settings.port,
                password=redis_settings.password,
                db=redis_settings.db,
                decode_responses=redis_settings.decode_responses,
            )
        return cls._instance

    @classmethod
    def get(cls, key: str) -> Optional[str]:
        try:
            client = cls.get_instance()
            return client.get(key)
        except Exception:
            return None

    @classmethod
    def set(cls, key: str, value: Any, ex: Optional[int] = None) -> bool:
        try:
            client = cls.get_instance()
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            client.set(key, value, ex=ex)
            return True
        except Exception:
            return False

    @classmethod
    def delete(cls, key: str) -> bool:
        try:
            client = cls.get_instance()
            client.delete(key)
            return True
        except Exception:
            return False

    @classmethod
    def exists(cls, key: str) -> bool:
        try:
            client = cls.get_instance()
            return bool(client.exists(key))
        except Exception:
            return False

    @classmethod
    def expire(cls, key: str, seconds: int) -> bool:
        try:
            client = cls.get_instance()
            client.expire(key, seconds)
            return True
        except Exception:
            return False


redis_client = RedisClient()
