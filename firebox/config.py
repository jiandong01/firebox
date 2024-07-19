import os
from firebox.models import FireboxConfig


def load_config(config_file: str = "firebox_config.yaml") -> FireboxConfig:
    if os.path.exists(config_file):
        return FireboxConfig.from_yaml(config_file)
    else:
        return FireboxConfig()


# Load configuration
config = load_config()
