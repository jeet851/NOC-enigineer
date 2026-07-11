from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select
from models.config_backup import ConfigurationBackup
from database.repositories.base import BaseRepository

class ConfigBackupRepository(BaseRepository[ConfigurationBackup]):
    def __init__(self):
        super().__init__(ConfigurationBackup)

    async def get_by_device(self, db: AsyncSession, device_name: str) -> List[ConfigurationBackup]:
        """
        Fetch all configuration backups for a specific device sorted by timestamp descending asynchronously.
        """
        stmt = select(ConfigurationBackup).where(ConfigurationBackup.device_name == device_name).order_by(ConfigurationBackup.timestamp.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_version(self, db: AsyncSession, device_name: str) -> int:
        """
        Get the highest version number of configuration backups for a device asynchronously.
        """
        stmt = select(ConfigurationBackup.version).where(ConfigurationBackup.device_name == device_name).order_by(ConfigurationBackup.version.desc()).limit(1)
        result = await db.execute(stmt)
        val = result.scalars().first()
        return val if val is not None else 0

    def get_by_device_sync(self, db: Session, device_name: str) -> List[ConfigurationBackup]:
        """
        Fetch all configuration backups for a specific device sorted by timestamp descending synchronously.
        """
        return db.query(ConfigurationBackup).filter(ConfigurationBackup.device_name == device_name).order_by(ConfigurationBackup.timestamp.desc()).all()

    def get_latest_version_sync(self, db: Session, device_name: str) -> int:
        """
        Get the highest version number of configuration backups for a device synchronously.
        """
        val = db.query(ConfigurationBackup.version).filter(ConfigurationBackup.device_name == device_name).order_by(ConfigurationBackup.version.desc()).first()
        return val[0] if val is not None else 0
