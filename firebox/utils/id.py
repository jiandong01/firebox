import random
import string

characters = string.ascii_letters + string.digits


def create_id(length: int) -> str:
    """
    Create a random ID of the specified length.

    :param length: The length of the ID to create
    :return: A random ID string
    """
    return "".join(random.choices(characters, k=length))
