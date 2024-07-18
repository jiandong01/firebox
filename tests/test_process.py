import pytest
import asyncio
from firebox.sandbox import Sandbox, SandboxConfig, Process, RunningProcess
from firebox.config import config
from firebox.logs import logger
from firebox.exceptions import TimeoutError


@pytest.fixture(scope="function")
def sandbox_config():
    return SandboxConfig(
        image_name=config.fireenv.sandbox.image_name,
        cpu=config.fireenv.sandbox.cpu,
        memory=config.fireenv.sandbox.memory,
        container_prefix=config.fireenv.sandbox.container_prefix,
        persistent_storage_path=config.fireenv.sandbox.persistent_storage_path,
        timeout=config.fireenv.sandbox.timeout,
    )


@pytest.fixture(scope="function")
async def sandbox(sandbox_config):
    s = Sandbox(sandbox_config)
    await s.init()
    yield s
    await s.close()


@pytest.fixture
def process(sandbox):
    return Process(sandbox)


@pytest.mark.asyncio
async def test_process_start(process):
    running_process = await process.start("echo 'Hello, World!'")
    assert isinstance(running_process, RunningProcess)
    assert running_process.pid > 0

    result = await running_process.wait(timeout=5)
    assert result["stdout"].strip() == "Hello, World!"
    assert result["exit_code"] == 0

    assert not await running_process.is_running()


@pytest.mark.asyncio
async def test_process_start_with_env_and_cwd(process):
    running_process = await process.start(
        "echo $TEST_VAR && pwd", env_vars={"TEST_VAR": "test_value"}, cwd="/tmp"
    )

    result = await running_process.wait()
    assert "test_value" in result["stdout"]
    assert "/tmp" in result["stdout"]
    assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_process_list(process):
    running_process = await process.start("sleep 2")
    processes = await process.list()

    assert len(processes) > 0
    assert any(str(running_process.pid) == str(p["pid"]) for p in processes)

    await running_process.wait()


@pytest.mark.asyncio
async def test_process_get(process):
    running_process = await process.start("sleep 2")
    retrieved_process = await process.get(running_process.pid)

    assert retrieved_process is not None
    assert retrieved_process.pid == running_process.pid

    await running_process.wait()


@pytest.mark.asyncio
async def test_process_send_stdin(process):
    running_process = await process.start("cat")
    await running_process.send_stdin("Hello, stdin!")
    await asyncio.sleep(1)
    await running_process.kill()
    result = await running_process.get_result()
    assert "Hello, stdin!" in result["stdout"]


@pytest.mark.asyncio
async def test_process_on_exit(process):
    exit_called = False

    def on_exit():
        nonlocal exit_called
        exit_called = True

    running_process = await process.start("echo 'Test'", on_exit=on_exit)
    await running_process.wait()

    assert exit_called


@pytest.mark.asyncio
async def test_multiple_processes(process):
    process1 = await process.start("echo 'Process 1'")
    process2 = await process.start("echo 'Process 2'")

    result1 = await process1.wait()
    result2 = await process2.wait()

    assert "Process 1" in result1["stdout"]
    assert "Process 2" in result2["stdout"]


@pytest.mark.asyncio
async def test_process_stream_output(process):
    logger.info("Starting test_process_stream_output")
    output = []

    def on_stdout(data):
        logger.debug(f"Received output: {data}")
        output.append(data.strip())

    running_process = await process.start(
        "echo 'Line 1' && sleep 1 && echo 'Line 2'", on_stdout=on_stdout
    )

    await running_process.wait()
    await asyncio.sleep(2)  # Give some time for the output to be processed

    logger.info(f"Collected output: {output}")
    assert len(output) == 2, f"Expected 2 lines of output, got {len(output)}"
    assert "Line 1" in output[0], f"Expected 'Line 1' in first output, got {output[0]}"
    assert "Line 2" in output[1], f"Expected 'Line 2' in second output, got {output[1]}"


@pytest.mark.asyncio
async def test_process_kill(process):
    logger.info("Starting test_process_kill")
    running_process = await process.start("sleep 10")
    await asyncio.sleep(0.5)  # Give some time for the process to start

    is_running = await running_process.is_running()
    logger.info(f"Process running status before kill: {is_running}")
    assert is_running, "Process should be running before kill"

    await running_process.kill()
    await asyncio.sleep(0.5)  # Give some time for the process to be killed

    is_running = await running_process.is_running()
    logger.info(f"Process running status after kill: {is_running}")
    assert (
        not is_running
    ), f"Process should not be running after kill, status: {await running_process._get_process_status()}"


@pytest.mark.asyncio
async def test_process_timeout(process):
    logger.info("Starting test_process_timeout")
    with pytest.raises(TimeoutError):
        running_process = await process.start("sleep 10")
        logger.info("Process started, waiting with timeout")
        await running_process.wait(timeout=2)
    logger.info("TimeoutError raised as expected")


@pytest.mark.asyncio
async def test_long_running_process(process):
    logger.info("Starting test_long_running_process")
    running_process = await process.start("sleep 2 && echo 'Done'")

    is_running = await running_process.is_running()
    logger.info(f"Process running status immediately after start: {is_running}")
    assert is_running, "Process should be running immediately after start"

    await asyncio.sleep(3)
    is_running = await running_process.is_running()
    logger.info(f"Process running status after sleep: {is_running}")
    assert not is_running, "Process should not be running after sleep"

    result = await running_process.get_result()
    logger.info(f"Process result: {result}")
    assert (
        "Done" in result["stdout"]
    ), f"Expected 'Done' in output, got {result['stdout']}"
