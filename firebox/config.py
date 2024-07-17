import os
from typing import Optional
from pydantic import BaseSettings, Field


class FireboxConfig(BaseSettings):
    api_key: Optional[str] = Field(None, env="FIREBOX_API_KEY")
    docker_host: str = Field("unix://var/run/docker.sock", env="FIREBOX_DOCKER_HOST")
    log_level: str = Field("INFO", env="FIREBOX_LOG_LEVEL")
    log_file: Optional[str] = Field(None, env="FIREBOX_LOG_FILE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


config = FireboxConfig()
