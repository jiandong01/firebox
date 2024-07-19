import os
from .config import config

# Sandbox constants
SANDBOX_REFRESH_PERIOD = 5  # seconds

# Timeout constants
TIMEOUT = 60  # seconds
LONG_TIMEOUT = 300  # seconds

# Security constants
SECURE = os.getenv("FIREBOX_SECURE", "TRUE").upper() == "TRUE"
DEBUG = config.debug

# Network constants
PROTOCOL = "https" if SECURE and not DEBUG else "http"
DOMAIN = os.getenv("FIREBOX_DOMAIN") or (DEBUG and "localhost") or "firebox.dev"
ENVD_PORT = 49982
WS_ROUTE = "/ws"
FILE_ROUTE = "/file"

# Process constants
MAX_PROCESS_OUTPUT = 1024 * 1024  # 1 MB

# Filesystem constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

# Terminal constants
DEFAULT_TERMINAL_COLS = 80
DEFAULT_TERMINAL_ROWS = 24

# Version
VERSION = "0.1.0"
