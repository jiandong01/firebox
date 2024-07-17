import pytest
from unittest.mock import Mock, patch
from firebox import Sandbox
from firebox.sandbox.exception import SandboxException, TimeoutException


@pytest.fixture
def mock_api_client():
    with patch("firebox.sandbox.main.E2BApiClient") as mock:
        yield mock


def test_sandbox_initialization(mock_api_client):
    sandbox = Sandbox(template="base")
    assert sandbox.template == "base"
    assert sandbox.cwd is None
    assert sandbox.env_vars == {}


def test_sandbox_with_custom_params(mock_api_client):
    sandbox = Sandbox(
        template="custom",
        cwd="/home/user",
        env_vars={"TEST": "VALUE"},
        api_key="test_key",
    )
    assert sandbox.template == "custom"
    assert sandbox.cwd == "/home/user"
    assert sandbox.env_vars == {"TEST": "VALUE"}
    assert sandbox._api_key == "test_key"


@patch("firebox.sandbox.main.SandboxConnection._open")
def test_sandbox_open(mock_open, mock_api_client):
    sandbox = Sandbox(template="base")
    mock_open.assert_called_once()


@patch("firebox.sandbox.main.SandboxConnection._open")
def test_sandbox_open_timeout(mock_open, mock_api_client):
    mock_open.side_effect = TimeoutException("Timeout")
    with pytest.raises(TimeoutException):
        Sandbox(template="base")


def test_sandbox_close():
    sandbox = Sandbox(template="base")
    sandbox._close = Mock()
    sandbox.close()
    sandbox._close.assert_called_once()


@patch("firebox.sandbox.main.Sandbox._open")
def test_sandbox_context_manager(mock_open):
    with Sandbox(template="base") as sandbox:
        assert isinstance(sandbox, Sandbox)
    sandbox._close.assert_called_once()
