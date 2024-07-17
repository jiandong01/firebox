import io
import tarfile
from typing import Dict, Optional
import aiodocker
from firebox.logging import logger
from firebox.exceptions import (
    DockerOperationError,
)


class DockerImageBuilder:
    def __init__(self, client: aiodocker.Docker):
        self.client = client

    async def build_image(
        self, dockerfile: str, tag: str, build_args: Optional[Dict[str, str]] = None
    ) -> str:
        try:
            logger.info(f"Building Docker image with tag: {tag}")
            dockerfile_obj = io.BytesIO(dockerfile.encode("utf-8"))
            tar_obj = io.BytesIO()
            tar = tarfile.open(fileobj=tar_obj, mode="w")
            tarinfo = tarfile.TarInfo(name="Dockerfile")
            tarinfo.size = len(dockerfile_obj.getvalue())
            tar.addfile(tarinfo, dockerfile_obj)
            tar.close()
            tar_obj.seek(0)

            build_result = await self.client.images.build(
                fileobj=tar_obj, encoding="utf-8", tag=tag, buildargs=build_args
            )
            image_id = build_result[0]["Id"]
            logger.info(f"Built image with ID: {image_id}")
            return image_id
        except aiodocker.exceptions.DockerError as e:
            raise DockerOperationError(f"Failed to build Docker image: {str(e)}")
