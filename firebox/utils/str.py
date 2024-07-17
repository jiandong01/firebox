import re


def camel_case_to_snake_case(text: str) -> str:
    """
    Convert a camelCase string to snake_case.

    :param text: The camelCase string to convert
    :return: The snake_case version of the string
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", text).lower()


def snake_case_to_camel_case(text: str) -> str:
    """
    Convert a snake_case string to camelCase.

    :param text: The snake_case string to convert
    :return: The camelCase version of the string
    """
    components = text.split("_")
    return components[0] + "".join(x.title() for x in components[1:])
