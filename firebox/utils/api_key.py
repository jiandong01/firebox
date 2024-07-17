import os
from typing import Optional

from firebox.sandbox.exception import AuthenticationException


def get_api_key(api_key: Optional[str]) -> str:
    """
    Retrieve the API key from the provided argument or environment variable.

    :param api_key: The API key provided as an argument
    :return: The API key to use
    :raises AuthenticationException: If no API key is found
    """
    api_key = api_key or os.getenv("FIREBOX_API_KEY")

    if api_key is None:
        raise AuthenticationException(
            "API key is required, please visit https://firebox.dev/docs to get your API key. "
            "You can either set the environment variable `FIREBOX_API_KEY` "
            'or you can pass it directly to the sandbox like Sandbox(api_key="firebox_...")',
        )

    return api_key
