from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select
from models.incident import Incident
from database.repositories.base import BaseRepository

class IncidentRepository(BaseRepository[Incident]):
    def __init__(self):
        super().__init__(Incident)

    async def get_active(self, db: AsyncSession) -> List[Incident]:
        """
        Retrieve all active incidents sorted by timestamp asynchronously.
        """
        stmt = select(Incident).where(Incident.status == "Active").order_by(Incident.timestamp.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_sorted(self, db: AsyncSession) -> List[Incident]:
        """
        Retrieve all incidents sorted by timestamp asynchronously.
        """
        stmt = select(Incident).order_by(Incident.timestamp.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def get_active_sync(self, db: Session) -> List[Incident]:
        """
        Retrieve all active incidents sorted by timestamp synchronously.
        """
        return db.query(Incident).filter(Incident.status == "Active").order_by(Incident.timestamp.desc()).all()

    def get_all_sorted_sync(self, db: Session) -> List[Incident]:
        """
        Retrieve all incidents sorted by timestamp synchronously.
        """
        return db.query(Incident).order_by(Incident.timestamp.desc()).all()
