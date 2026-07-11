from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from models.device import Device
from database.repositories.device import DeviceRepository
from typing import List, Optional

class DeviceService:
    device_repo = DeviceRepository()

    # --- Synchronous Methods (Backward Compatibility) ---

    @staticmethod
    def get_all_devices(db: Session) -> List[Device]:
        return DeviceService.device_repo.get_all_sync(db)

    @staticmethod
    def get_device_by_name(db: Session, name: str) -> Optional[Device]:
        return DeviceService.device_repo.get_by_name_sync(db, name)

    @staticmethod
    def update_device_status(db: Session, name: str, status: str) -> bool:
        device = DeviceService.device_repo.get_by_name_sync(db, name)
        if device:
            DeviceService.device_repo.update_sync(db, device, {"status": status})
            return True
        return False

    @staticmethod
    def create_device(
        db: Session,
        name: str,
        ip: str,
        vendor: str,
        platform: str,
        status: str,
        role: str,
        site: str,
        description: Optional[str] = None
    ) -> Device:
        device = Device(
            name=name,
            ip=ip,
            vendor=vendor,
            platform=platform,
            status=status,
            role=role,
            site=site,
            description=description
        )
        return DeviceService.device_repo.create_sync(db, device)

    # --- Asynchronous Methods (for FastAPI) ---

    @staticmethod
    async def get_all_devices_async(db: AsyncSession) -> List[Device]:
        return await DeviceService.device_repo.get_all(db)

    @staticmethod
    async def get_device_by_name_async(db: AsyncSession, name: str) -> Optional[Device]:
        return await DeviceService.device_repo.get_by_name(db, name)

    @staticmethod
    async def update_device_status_async(db: AsyncSession, name: str, status: str) -> bool:
        device = await DeviceService.device_repo.get_by_name(db, name)
        if device:
            await DeviceService.device_repo.update(db, device, {"status": status})
            return True
        return False

    @staticmethod
    async def create_device_async(
        db: AsyncSession,
        name: str,
        ip: str,
        vendor: str,
        platform: str,
        status: str,
        role: str,
        site: str,
        description: Optional[str] = None
    ) -> Device:
        device = Device(
            name=name,
            ip=ip,
            vendor=vendor,
            platform=platform,
            status=status,
            role=role,
            site=site,
            description=description
        )
        return await DeviceService.device_repo.create(db, device)
