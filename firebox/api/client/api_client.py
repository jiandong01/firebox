import docker
from typing import Dict, Optional


class ApiClient:
    def __init__(self, configuration=None):
        self.configuration = configuration or Configuration()
        self.docker_client = docker.from_env()

    def call_api(
        self,
        method,
        resource_path,
        path_params=None,
        query_params=None,
        header_params=None,
        body=None,
        **kwargs
    ):
        # This method can be implemented if needed for compatibility,
        # but most calls will be handled directly by the SandboxesApi class
        pass
