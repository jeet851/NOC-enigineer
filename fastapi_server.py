import os
import logging
import uvicorn
from dotenv import load_dotenv

load_dotenv()

# Initialize structured logging before importing anything else
from core.logger import setup_logging
setup_logging()

logger = logging.getLogger("noc.startup")

# Import the ASGI-wrapped modular application (incorporating FastAPI + Socket.IO)
from api.app import app_asgi
from api.config import settings

if __name__ == "__main__":
    host = settings.BIND_HOST
    port = settings.PORT

    cert_path = settings.SSL_CERT_PATH
    key_path = settings.SSL_KEY_PATH

    ssl_context_args = {}
    if os.path.exists(cert_path) and os.path.exists(key_path):
        ssl_context_args["ssl_keyfile"] = key_path
        ssl_context_args["ssl_certfile"] = cert_path
        logger.info(
            "Starting AIOps Copilot NOC Dashboard",
            extra={"scheme": "https", "host": host, "port": port}
        )
    else:
        logger.info(
            "Starting AIOps Copilot NOC Dashboard (HTTP fallback — no SSL certs found)",
            extra={"scheme": "http", "host": host, "port": port}
        )

    uvicorn.run(
        "api.app:app_asgi",
        host=host,
        port=port,
        reload=(settings.APP_ENV == "development"),
        log_level=settings.LOG_LEVEL.lower(),
        **ssl_context_args
    )
