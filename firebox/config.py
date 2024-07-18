import os
from typing import Dict, Any
import yaml
from pydantic import BaseSettings, Field


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
    default_cpu: int = Field(default=1, env="FIREBOX_DEFAULT_CPU")
    default_memory: str = Field(default="1g", env="FIREBOX_DEFAULT_MEMORY")
    default_timeout: int = Field(default=30, env="FIREBOX_DEFAULT_TIMEOUT")
    docker_host: str = Field(
        default="unix://var/run/docker.sock", env="FIREBOX_DOCKER_HOST"
    )

    @classmethod
    def from_yaml(cls, yaml_file: str) -> "FireboxConfig":
        with open(yaml_file, "r") as f:
            config_dict = yaml.safe_load(f)
        return cls(**config_dict)


config = FireboxConfig()


def load_config(config_file: str = "firebox_config.yaml"):
    global config
    if os.path.exists(config_file):
        config = FireboxConfig.from_yaml(config_file)
    else:
        config = FireboxConfig()
