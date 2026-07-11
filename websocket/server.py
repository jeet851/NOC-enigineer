import socketio
from api.config import settings

# Setup Socket.IO async server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)

# Create ASGI wrapper for mounting onto FastAPI
socket_app = socketio.ASGIApp(
    socketio_server=sio,
    socketio_path=""
)
