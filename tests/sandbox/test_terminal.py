import pytest
from unittest.mock import Mock, patch
from firebox.sandbox.terminal import TerminalManager, Terminal
from firebox.sandbox.exception import TerminalException


@pytest.fixture
def mock_sandbox_connection():
    return Mock()


@pytest.fixture
def terminal_manager(mock_sandbox_connection):
    return TerminalManager(mock_sandbox_connection)


def test_start_terminal(terminal_manager, mock_sandbox_connection):
    mock_sandbox_connection._call.return_value = None
    mock_sandbox_connection._handle_subscriptions.return_value = Mock()

    on_data = Mock()
    terminal = terminal_manager.start(on_data, cols=80, rows=24)

    assert isinstance(terminal, Terminal)
    mock_sandbox_connection._call.assert_called_with(
        "terminal", "start", [terminal.terminal_id, 80, 24, {}, None, ""], timeout=60
    )


def test_terminal_send_data(terminal_manager, mock_sandbox_connection):
    mock_sandbox_connection._call.return_value = None
    mock_sandbox_connection._handle_subscriptions.return_value = Mock()

    terminal = terminal_manager.start(Mock(), cols=80, rows=24)
    terminal.send_data("ls -l")

    mock_sandbox_connection._call.assert_called_with(
        "terminal", "data", [terminal.terminal_id, "ls -l"], timeout=60
    )


def test_terminal_resize(terminal_manager, mock_sandbox_connection):
    mock_sandbox_connection._call.return_value = None
    mock_sandbox_connection._handle_subscriptions.return_value = Mock()

    terminal = terminal_manager.start(Mock(), cols=80, rows=24)
    terminal.resize(100, 30)

    mock_sandbox_connection._call.assert_called_with(
        "terminal", "resize", [terminal.terminal_id, 100, 30], timeout=60
    )


def test_terminal_kill(terminal_manager, mock_sandbox_connection):
    mock_sandbox_connection._call.return_value = None
    mock_sandbox_connection._handle_subscriptions.return_value = Mock()

    terminal = terminal_manager.start(Mock(), cols=80, rows=24)
    terminal.kill()

    mock_sandbox_connection._call.assert_called_with(
        "terminal", "destroy", [terminal.terminal_id], timeout=60
    )
