from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from models.device import Device
from database.repositories.base import BaseRepository

class DeviceRepository(BaseRepository[Device]):
    def __init__(self):
        super().__init__(Device)

    async def get_by_name(self, db: AsyncSession, name: str, include_interfaces: bool = False) -> Optional[Device]:
        """
        Fetch a device by name, optionally loading its associated interfaces asynchronously.
        """
        stmt = select(Device).where(Device.name == name)
        if include_interfaces:
            stmt = stmt.options(selectinload(Device.interfaces))
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_all_with_interfaces(self, db: AsyncSession) -> List[Device]:
        """
        Fetch all devices with interfaces loaded asynchronously.
        """
        stmt = select(Device).options(selectinload(Device.interfaces))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def get_by_name_sync(self, db: Session, name: str, include_interfaces: bool = False) -> Optional[Device]:
        """
        Fetch a device by name, optionally loading its associated interfaces synchronously.
        """
        query = db.query(Device).filter(Device.name == name)
        if include_interfaces:
            query = query.options(selectinload(Device.interfaces))
        return query.first()

    def get_all_with_interfaces_sync(self, db: Session) -> List[Device]:
        """
        Fetch all devices with interfaces loaded synchronously.
        """
        return db.query(Device).options(selectinload(Device.interfaces)).all()
