import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

# Import the ASGI-wrapped modular application (incorporating FastAPI + Socket.IO)
from api.app import app_asgi

if __name__ == "__main__":
    host = os.environ.get("BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5001))
    
    cert_path = os.environ.get("SSL_CERT_PATH", "localhost.crt")
    key_path = os.environ.get("SSL_KEY_PATH", "localhost.key")
    
    ssl_context_args = {}
    if os.path.exists(cert_path) and os.path.exists(key_path):
        ssl_context_args["ssl_keyfile"] = key_path
        ssl_context_args["ssl_certfile"] = cert_path
        print(f"Starting AIOps Copilot FastAPI Dashboard on https://{host}:{port} (HTTPS Active)")
    else:
        print(f"Starting AIOps Copilot FastAPI Dashboard on http://{host}:{port} (HTTP Fallback)")
        
    uvicorn.run("api.app:app_asgi", host=host, port=port, reload=True, **ssl_context_args)
