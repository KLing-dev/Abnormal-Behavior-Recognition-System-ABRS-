from pydantic_settings import BaseSettings
from typing import Optional


class RabbitMQSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5672
    username: str = "guest"
    password: str = "guest"
    virtual_host: str = "/"

    @property
    def url(self) -> str:
        return f"amqp://{self.username}:{self.password}@{self.host}:{self.port}{self.virtual_host}"

    class Config:
        env_prefix = "RABBITMQ_"


rabbitmq_settings = RabbitMQSettings()
