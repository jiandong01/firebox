# firebox/api/aync_docker_adapter.py

import asyncio
import aiodocker
import tarfile
import io
import os
from typing import Dict, Optional, List
from datetime import datetime
from firebox.api.models import (
    Sandbox,
    NewSandbox,
    RunningSandboxes,
)
from firebox.exceptions import (
    SandboxCreationError,
    SandboxNotFoundError,
    DockerOperationError,
)
from firebox.config import config
from firebox.logging import logger
from firebox.cleanup import cleanup_manager


class AsyncDockerAdapter:
    def __init__(self):
        self.client = None
        cleanup_manager.add_task(self.close)

    async def _get_client(self):
        if self.client is None:
            # self.client = aiodocker.Docker(url=config.docker_host)
            self.client = aiodocker.Docker()
        return self.client

    async def build_image(
        self, dockerfile: str, tag: str, build_args: Optional[Dict[str, str]] = None
    ) -> str:
        try:
            client = await self._get_client()

            # Create a tar archive containing the Dockerfile
            dockerfile_obj = io.BytesIO(dockerfile.encode("utf-8"))
            tar_obj = io.BytesIO()
            with tarfile.open(fileobj=tar_obj, mode="w") as tar:
                tarinfo = tarfile.TarInfo(name="Dockerfile")
                tarinfo.size = len(dockerfile_obj.getvalue())
                tar.addfile(tarinfo, dockerfile_obj)
            tar_obj.seek(0)

            build_generator = client.images.build(
                fileobj=tar_obj,
                encoding="utf-8",
                tag=tag,
                buildargs=build_args,
                stream=True,
            )

            image_id = None
            async for chunk in build_generator:
                if isinstance(chunk, dict):
                    if "stream" in chunk:
                        print(chunk["stream"].strip())
                    if "aux" in chunk and "ID" in chunk["aux"]:
                        image_id = chunk["aux"]["ID"]
                elif isinstance(chunk, str):
                    print(chunk.strip())

            if not image_id:
                raise SandboxCreationError("Failed to build Docker image")

            return image_id

        except aiodocker.exceptions.DockerError as e:
            raise SandboxCreationError(f"Failed to build Docker image: {str(e)}")

    async def create_sandbox(self, new_sandbox: NewSandbox) -> Sandbox:
        logger.info(f"Creating sandbox with template: {new_sandbox.template_id}")

        try:
            client = await self._get_client()

            # If a Dockerfile is provided, build the image first
            if new_sandbox.dockerfile:
                image_tag = f"firebox-custom-{new_sandbox.template_id}"
                image_id = await self.build_image(
                    new_sandbox.dockerfile, image_tag, new_sandbox.build_args
                )
            else:
                image_id = new_sandbox.template_id

            container_config = {
                "Image": image_id,
                "Env": [f"{k}={v}" for k, v in (new_sandbox.metadata or {}).items()],
                "HostConfig": {
                    "CpuCount": new_sandbox.cpu_count,
                    "Memory": (
                        new_sandbox.memory_mb * 1024 * 1024
                        if new_sandbox.memory_mb
                        else None
                    ),
                    "PublishAllPorts": True,
                    "SecurityOpt": ["no-new-privileges:true"],
                    "CapDrop": ["ALL"],
                    "CapAdd": new_sandbox.capabilities or [],
                },
            }

            if new_sandbox.ports:
                container_config["ExposedPorts"] = {
                    f"{port}/tcp": {} for port in new_sandbox.ports.values()
                }
                container_config["HostConfig"]["PortBindings"] = {
                    f"{container}/tcp": [{"HostPort": str(host)}]
                    for host, container in new_sandbox.ports.items()
                }

            if new_sandbox.volumes:
                container_config["HostConfig"]["Binds"] = [
                    f"{host}:{container}"
                    for host, container in new_sandbox.volumes.items()
                ]

            container = await client.containers.create(config=container_config)
            await container.start()

            return Sandbox(
                template_id=new_sandbox.template_id,
                sandbox_id=container.id[:12],
                client_id="local",
                alias=(
                    new_sandbox.metadata.get("alias") if new_sandbox.metadata else None
                ),
            )
        except aiodocker.exceptions.DockerError as e:
            raise SandboxCreationError(f"Failed to create sandbox: {str(e)}")

    async def list_sandboxes(self) -> List[RunningSandboxes]:
        try:
            containers = await self.client.containers.list()
            running_sandboxes = []
            for container in containers:
                inspect = await container.show()
                running_sandboxes.append(
                    RunningSandboxes(
                        template_id=inspect["Config"]["Image"],
                        sandbox_id=container.id[:12],
                        client_id="local",
                        started_at=datetime.fromisoformat(
                            inspect["State"]["StartedAt"].rstrip("Z")
                        ),
                        cpu_count=inspect["HostConfig"]["CpuCount"] or 0,
                        memory_mb=(
                            inspect["HostConfig"]["Memory"] // (1024 * 1024)
                            if inspect["HostConfig"]["Memory"]
                            else 0
                        ),
                        metadata=inspect["Config"]["Labels"],
                    )
                )
            return running_sandboxes
        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to list sandboxes: {str(e)}")

    async def delete_sandbox(self, sandbox_id: str):
        try:
            container = await self.client.containers.get(sandbox_id)
            await container.delete(force=True)
        except aiodocker.exceptions.DockerError as e:
            if e.status == 404:
                raise SandboxNotFoundError(f"Sandbox with ID {sandbox_id} not found")
            raise DockerOperationError(f"Failed to delete sandbox: {str(e)}")

    async def get_sandbox_logs(
        self, sandbox_id: str, start: Optional[int] = None, limit: Optional[int] = None
    ) -> str:
        try:
            container = await self.client.containers.get(sandbox_id)
            logs = await container.log(
                stdout=True,
                stderr=True,
                since=0 if start is None else start,  # Use 0 if start is None
                tail=limit,
            )
            return "".join(logs)
        except aiodocker.exceptions.DockerError as e:
            if e.status == 404:
                raise SandboxNotFoundError(f"Sandbox with ID {sandbox_id} not found")
            raise DockerOperationError(f"Failed to get sandbox logs: {str(e)}")

    async def refresh_sandbox(self, sandbox_id: str, duration: int):
        # For Docker, we don't need to refresh. This method can be a no-op.
        pass

    # File Upload/Download

    async def upload_file(
        self, sandbox_id: str, file_content: bytes, container_path: str
    ):
        try:
            container = await self.client.containers.get(sandbox_id)

            # Create a tar archive containing the file
            tar_buffer = io.BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                file_data = io.BytesIO(file_content)
                tarinfo = tarfile.TarInfo(name=os.path.basename(container_path))
                tarinfo.size = len(file_content)
                tar.addfile(tarinfo, file_data)

            tar_buffer.seek(0)
            await container.put_archive(os.path.dirname(container_path), tar_buffer)

            logger.debug(f"File uploaded to {container_path}")

        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to upload file: {str(e)}")

    async def download_file(self, sandbox_id: str, container_path: str) -> bytes:
        try:
            container = await self.client.containers.get(sandbox_id)

            tar_stream, _ = await container.get_archive(container_path)

            tar_content = await tar_stream.read()
            tar_buffer = io.BytesIO(tar_content)

            with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                file = tar.extractfile(os.path.basename(container_path))
                if file is None:
                    raise ValueError(
                        f"Failed to extract file {container_path} from archive"
                    )
                return file.read()

        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to download file: {str(e)}")

    async def list_files(self, sandbox_id: str, path: str) -> List[Dict[str, str]]:
        try:
            container = await self.client.containers.get(sandbox_id)

            # Use exec to list directory contents
            exec_result = await container.exec(cmd=f"ls -la {path}", user="root")

            if exec_result.exit_code != 0:
                raise DockerOperationError(
                    f"Failed to list files: {exec_result.output.decode()}"
                )

            output_str = exec_result.output.decode("utf-8")
            logger.debug(f"ls -la output: {output_str}")

            files = []
            for line in output_str.split("\n")[1:]:  # Skip the first line (total)
                if line.strip():
                    parts = line.split(None, 8)
                    if len(parts) >= 9:
                        file_info = {
                            "name": parts[8],
                            "type": "directory" if parts[0].startswith("d") else "file",
                            "size": parts[4],
                            "permissions": parts[0],
                        }
                        logger.debug(f"File info: {file_info}")
                        files.append(file_info)

            return files
        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to list files: {str(e)}")

    # Network Management

    async def create_network(self, network_name: str):
        try:
            network = await self.client.networks.create(
                {
                    "Name": network_name,
                    "Driver": "bridge",
                }
            )
            return network.id
        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to create network: {str(e)}")

    async def connect_to_network(self, sandbox_id: str, network_id: str):
        try:
            container = await self.client.containers.get(sandbox_id)
            network = await self.client.networks.get(network_id)
            await network.connect({"Container": container.id})
        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to connect to network: {str(e)}")

    async def disconnect_from_network(self, sandbox_id: str, network_id: str):
        try:
            container = await self.client.containers.get(sandbox_id)
            network = await self.client.networks.get(network_id)
            await network.disconnect({"Container": container.id})
        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to disconnect from network: {str(e)}")

    # Secret

    async def create_secret(self, name: str, data: str) -> str:
        try:
            secret = await self.client.secrets.create(
                {
                    "Name": name,
                    "Data": data,
                }
            )
            return secret["ID"]
        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to create secret: {str(e)}")

    async def attach_secret_to_sandbox(
        self, sandbox_id: str, secret_id: str, target_file: str
    ):
        try:
            container = await self.client.containers.get(sandbox_id)
            await container.update(
                secrets=[
                    {
                        "SecretID": secret_id,
                        "SecretName": secret_id,
                        "File": {
                            "Name": target_file,
                            "UID": "0",
                            "GID": "0",
                            "Mode": 0o400,
                        },
                    }
                ]
            )
        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to attach secret to sandbox: {str(e)}")

    # Health Check

    async def check_sandbox_health(self, sandbox_id: str) -> dict:
        try:
            container = await self.client.containers.get(sandbox_id)
            inspect_result = await container.show()
            health_status = (
                inspect_result.get("State", {})
                .get("Health", {})
                .get("Status", "unknown")
            )
            return {
                "status": health_status,
                "running": inspect_result["State"]["Running"],
                "exit_code": inspect_result["State"]["ExitCode"],
            }
        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to check sandbox health: {str(e)}")

    # Status Check

    async def get_sandbox_stats(self, sandbox_id: str) -> dict:
        try:
            container = await self.client.containers.get(sandbox_id)
            stats = await container.stats(stream=False)
            return {
                "cpu_usage": stats["cpu_stats"]["cpu_usage"]["total_usage"],
                "memory_usage": stats["memory_stats"]["usage"],
                "network_rx": stats["networks"]["eth0"]["rx_bytes"],
                "network_tx": stats["networks"]["eth0"]["tx_bytes"],
            }
        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to get sandbox stats: {str(e)}")

    async def get_container_info(self, sandbox_id: str):
        container = await self.client.containers.get(sandbox_id)
        info = await container.show()
        return info

    # Close

    async def close(self):
        logger.info("Closing Docker client ...")
        await self.client.close()
