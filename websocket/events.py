from websocket.server import sio
import logging

logger = logging.getLogger("websocket")

@sio.event
async def connect(sid, environ):
    logger.info(f"Socket.IO client connected: {sid}")
    print(f"Socket.IO client connected: {sid}")
    # Immediately send a welcome ping
    await sio.emit("welcome", {"message": "NOC Real-Time Telemetry Link Established"}, to=sid)

@sio.event
async def disconnect(sid):
    logger.info(f"Socket.IO client disconnected: {sid}")
    print(f"Socket.IO client disconnected: {sid}")

async def broadcast_telemetry(data: dict):
    """
    Broadcasts live telemetry data to all connected socket clients.
    """
    await sio.emit("telemetry_update", data)

async def broadcast_alarm(data: dict):
    """
    Broadcasts triggered alarms to all connected socket clients.
    """
    await sio.emit("alarm_update", data)
