import pytest
from unittest.mock import Mock, patch
from firebox.sandbox.process import ProcessManager, Process, ProcessOutput
from firebox.sandbox.exception import ProcessException


@pytest.fixture
def mock_sandbox_connection():
    return Mock()


@pytest.fixture
def process_manager(mock_sandbox_connection):
    return ProcessManager(mock_sandbox_connection)


def test_start_process(process_manager, mock_sandbox_connection):
    mock_sandbox_connection._call.return_value = "process_id"
    mock_sandbox_connection._handle_subscriptions.return_value = Mock()

    process = process_manager.start("echo Hello")

    assert isinstance(process, Process)
    assert process.process_id == "process_id"
    mock_sandbox_connection._call.assert_called_with(
        "process", "start", ["process_id", "echo Hello", {}, ""], timeout=60
    )


def test_process_wait(process_manager, mock_sandbox_connection):
    mock_sandbox_connection._call.return_value = "process_id"
    mock_sandbox_connection._handle_subscriptions.return_value = Mock()

    process = process_manager.start("echo Hello")
    process._finished.set_result(ProcessOutput(exit_code=0))

    result = process.wait()
    assert isinstance(result, ProcessOutput)
    assert result.exit_code == 0


def test_process_send_stdin(process_manager, mock_sandbox_connection):
    mock_sandbox_connection._call.return_value = "process_id"
    mock_sandbox_connection._handle_subscriptions.return_value = Mock()

    process = process_manager.start("cat")
    process.send_stdin("Hello")

    mock_sandbox_connection._call.assert_called_with(
        "process", "stdin", ["process_id", "Hello"], timeout=60
    )


def test_process_kill(process_manager, mock_sandbox_connection):
    mock_sandbox_connection._call.return_value = "process_id"
    mock_sandbox_connection._handle_subscriptions.return_value = Mock()

    process = process_manager.start("sleep 100")
    process.kill()

    mock_sandbox_connection._call.assert_called_with(
        "process", "kill", ["process_id"], timeout=60
    )
