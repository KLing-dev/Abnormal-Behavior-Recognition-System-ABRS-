from pydantic_settings import BaseSettings
from typing import Optional


class DatabaseSettings(BaseSettings):
    host: str = "localhost"
    port: int = 3308
    username: str = "root"
    password: str = "root123"
    database: str = "abrs"
    charset: str = "utf8mb4"

    @property
    def url(self) -> str:
        return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}"

    class Config:
        env_prefix = "DB_"


db_settings = DatabaseSettings()
