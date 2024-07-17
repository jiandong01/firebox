from typing import Dict

EnvVars = Dict[str, str]


def merge_env_vars(base: EnvVars, override: EnvVars) -> EnvVars:
    """
    Merge two sets of environment variables, with override taking precedence.

    :param base: The base set of environment variables
    :param override: The set of environment variables to override the base
    :return: A merged dictionary of environment variables
    """
    return {**base, **override}


def sanitize_env_vars(env_vars: EnvVars) -> EnvVars:
    """
    Sanitize environment variables by ensuring all values are strings.

    :param env_vars: The environment variables to sanitize
    :return: A sanitized dictionary of environment variables
    """
    return {k: str(v) for k, v in env_vars.items()}


def format_env_vars(env_vars: EnvVars) -> str:
    """
    Format environment variables for display or logging.

    :param env_vars: The environment variables to format
    :return: A formatted string representation of the environment variables
    """
    return " ".join(f"{k}={v}" for k, v in env_vars.items())
