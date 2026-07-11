from sqlalchemy.ext.asyncio import AsyncSession
from models.audit import AuditLog
from database.repositories.base import BaseRepository

class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self):
        super().__init__(AuditLog)
