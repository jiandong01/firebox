import pytest
from firebox.utils import (
    get_api_key,
    resolve_path,
    create_id,
    camel_case_to_snake_case,
    snake_case_to_camel_case,
)
from firebox.sandbox.exception import AuthenticationException


def test_get_api_key():
    assert get_api_key("test_key") == "test_key"
    with pytest.raises(AuthenticationException):
        get_api_key(None)


def test_resolve_path():
    assert resolve_path("/absolute/path") == "/absolute/path"
    assert resolve_path("relative/path", cwd="/home/user") == "/home/user/relative/path"
    assert resolve_path("~/path") == "/home/user/path"
    with pytest.warns(UserWarning):
        assert resolve_path("./path") == "/home/user/path"


def test_create_id():
    id1 = create_id(10)
    id2 = create_id(10)
    assert len(id1) == 10
    assert len(id2) == 10
    assert id1 != id2


def test_camel_case_to_snake_case():
    assert camel_case_to_snake_case("camelCase") == "camel_case"
    assert camel_case_to_snake_case("ThisIsATest") == "this_is_a_test"


def test_snake_case_to_camel_case():
    assert snake_case_to_camel_case("snake_case") == "snakeCase"
    assert snake_case_to_camel_case("this_is_a_test") == "thisIsATest"
