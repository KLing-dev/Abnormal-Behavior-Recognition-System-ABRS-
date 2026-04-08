from pydantic_settings import BaseSettings
from typing import Optional


class AppSettings(BaseSettings):
    app_name: str = "ABRS"
    version: str = "1.0.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    cors_origins: list = ["*"]

    class Config:
        env_prefix = "APP_"


app_settings = AppSettings()
