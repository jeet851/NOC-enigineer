import psutil
from sqlalchemy import text
from database.session import engine, async_engine
import redis
import pika
from api.config import settings

class SystemHealthMonitor:
    @staticmethod
    def get_database_status() -> str:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return "Healthy"
        except Exception as e:
            return f"Unhealthy (Error: {str(e)})"

    @staticmethod
    async def get_database_status_async() -> str:
        try:
            async with async_engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return "Healthy"
        except Exception as e:
            return f"Unhealthy (Error: {str(e)})"

    @staticmethod
    def get_redis_status() -> str:
        try:
            r = redis.from_url(settings.REDIS_URL, socket_timeout=1)
            r.ping()
            return "Healthy"
        except Exception as e:
            return f"Unhealthy (Error: {str(e)})"

    @staticmethod
    def get_rabbitmq_status() -> str:
        try:
            parameters = pika.URLParameters(settings.RABBITMQ_URL)
            parameters.socket_timeout = 1
            connection = pika.BlockingConnection(parameters)
            connection.close()
            return "Healthy"
        except Exception as e:
            return f"Unhealthy (Error: {str(e)})"

    @staticmethod
    def get_system_load() -> dict:
        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent
        }
