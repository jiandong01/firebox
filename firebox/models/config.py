import os
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FireboxConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    sandbox_image: str = Field(
        default="firebox-sandbox:latest",
        description="Docker image for the sandbox",
        json_schema_extra={"env": "FIREBOX_SANDBOX_IMAGE"},
    )
    container_prefix: str = Field(
        default="firebox-sandbox",
        description="Prefix for container names",
        json_schema_extra={"env": "FIREBOX_CONTAINER_PREFIX"},
    )
    persistent_storage_path: str = Field(
        default="/persistent",
        description="Path for persistent storage in the sandbox",
        json_schema_extra={"env": "FIREBOX_PERSISTENT_STORAGE_PATH"},
    )
    cpu: int = Field(
        default=1,
        description="Default CPU allocation for sandboxes",
        json_schema_extra={"env": "FIREBOX_DEFAULT_CPU"},
    )
    memory: str = Field(
        default="1g",
        description="Default memory allocation for sandboxes",
        json_schema_extra={"env": "FIREBOX_DEFAULT_MEMORY"},
    )
    timeout: int = Field(
        default=60,
        description="Default timeout for operations (in seconds)",
        json_schema_extra={"env": "FIREBOX_DEFAULT_TIMEOUT"},
    )
    docker_host: str = Field(
        default="unix://var/run/docker.sock",
        description="Docker host URL",
        json_schema_extra={"env": "FIREBOX_DOCKER_HOST"},
    )
    debug: bool = Field(
        default=False,
        description="Debug mode flag",
        json_schema_extra={"env": "FIREBOX_DEBUG"},
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
        json_schema_extra={"env": "FIREBOX_LOG_LEVEL"},
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries for operations",
        json_schema_extra={"env": "FIREBOX_MAX_RETRIES"},
    )
    retry_delay: float = Field(
        default=1.0,
        description="Delay between retries (in seconds)",
        json_schema_extra={"env": "FIREBOX_RETRY_DELAY"},
    )

    @classmethod
    def from_yaml(cls, yaml_file: str) -> "FireboxConfig":
        with open(yaml_file, "r") as f:
            config_dict = yaml.safe_load(f)
        return cls(**config_dict)
