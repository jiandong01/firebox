import os
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class FireboxConfig(BaseSettings):
    sandbox_image: str = Field(
        default="fireenv-sandbox:latest", env="FIREBOX_SANDBOX_IMAGE"
    )
    container_prefix: str = Field(
        default="fireenv-sandbox", env="FIREBOX_CONTAINER_PREFIX"
    )
    persistent_storage_path: str = Field(
        default="/persistent", env="FIREBOX_PERSISTENT_STORAGE_PATH"
    )
    cpu: int = Field(default=1, env="FIREBOX_DEFAULT_CPU")
    memory: str = Field(default="1g", env="FIREBOX_DEFAULT_MEMORY")
    timeout: int = Field(default=60, env="FIREBOX_DEFAULT_TIMEOUT")
    docker_host: str = Field(
        default="unix://var/run/docker.sock", env="FIREBOX_DOCKER_HOST"
    )
    debug: bool = Field(default=False, env="FIREBOX_DEBUG")
    log_level: str = Field(default="INFO", env="FIREBOX_LOG_LEVEL")
    max_retries: int = Field(default=3, env="FIREBOX_MAX_RETRIES")
    retry_delay: float = Field(default=1.0, env="FIREBOX_RETRY_DELAY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @classmethod
    def from_yaml(cls, yaml_file: str) -> "FireboxConfig":
        with open(yaml_file, "r") as f:
            config_dict = yaml.safe_load(f)
        return cls(**config_dict)


def load_config(config_file: str = "firebox_config.yaml") -> FireboxConfig:
    if os.path.exists(config_file):
        return FireboxConfig.from_yaml(config_file)
    else:
        return FireboxConfig()


# Load configuration
config = load_config()
