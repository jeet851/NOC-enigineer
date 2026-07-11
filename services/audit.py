from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select
from models.audit import AuditLog
from datetime import datetime
from typing import List, Optional, Any

class AuditService:
    # --- Synchronous Methods (for Celery & Sync Callers) ---

    @staticmethod
    def log_audit_event(
        db: Session,
        user_name: str,
        role: str,
        action: str,
        ip: str,
        details: str,
        status: str = "Success",
        changes: Optional[str] = None,
        approvals: Optional[str] = None,
        rollback: Optional[str] = None
    ) -> AuditLog:
        event = AuditLog(
            timestamp=datetime.utcnow(),
            user_name=user_name,
            role=role,
            action=action,
            ip=ip,
            details=details,
            status=status,
            changes=changes,
            approvals=approvals,
            rollback=rollback
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def get_audit_logs_sync(db: Session, limit: int = 100) -> List[AuditLog]:
        return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()

    # --- Asynchronous Methods (for FastAPI / AsyncSession) ---

    @staticmethod
    async def log_audit_event_async(
        db: AsyncSession,
        user_name: str,
        role: str,
        action: str,
        ip: str,
        details: str,
        status: str = "Success",
        changes: Optional[str] = None,
        approvals: Optional[str] = None,
        rollback: Optional[str] = None
    ) -> AuditLog:
        event = AuditLog(
            timestamp=datetime.utcnow(),
            user_name=user_name,
            role=role,
            action=action,
            ip=ip,
            details=details,
            status=status,
            changes=changes,
            approvals=approvals,
            rollback=rollback
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def get_audit_logs(db: AsyncSession, limit: int = 100) -> List[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())
