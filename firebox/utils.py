import asyncio
from docker import DockerClient
from docker.errors import BuildError
from .logs import logger


async def build_docker_image(
    client: DockerClient, dockerfile: str, context: str, tag: str
):
    logger.info(f"Building Docker image from {dockerfile} with tag {tag}")
    try:
        # Use asyncio to run the blocking Docker build operation in a separate thread
        image, build_logs = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.images.build(
                path=context,
                dockerfile=dockerfile,
                tag=tag,
                rm=True,
                forcerm=True,
            ),
        )
        for log in build_logs:
            if "stream" in log:
                logger.info(log["stream"].strip())
        logger.info(f"Successfully built image: {tag}")
        return image
    except BuildError as e:
        logger.error(f"Error building Docker image: {str(e)}")
        raise
