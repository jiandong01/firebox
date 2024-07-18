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
    cpu: int = Field(default=1, env="FIREBOX_DEFAULT_CPU")
    memory: str = Field(default="1g", env="FIREBOX_DEFAULT_MEMORY")
    timeout: int = Field(default=30, env="FIREBOX_DEFAULT_TIMEOUT")
    docker_host: str = Field(default="tcp://localhost:2375", env="FIREBOX_DOCKER_HOST")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
