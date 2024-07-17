import os

SANDBOX_REFRESH_PERIOD = 5  # seconds
TIMEOUT = 60

SECURE = os.getenv("FIREBOX_SECURE", "TRUE").upper() == "TRUE"
DEBUG = os.getenv("FIREBOX_DEBUG") or False
PROTOCOL = "https" if SECURE and not DEBUG else "http"

DOMAIN = (
    os.getenv("FIREBOX_DOMAIN") or (DEBUG and "localhost:3000") or "api.firebox.dev"
)

ENVD_PORT = 49982
WS_ROUTE = "/ws"
FILE_ROUTE = "/file"
