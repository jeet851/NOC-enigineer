from typing import Generic, TypeVar, Type, List, Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

T = TypeVar("T")

class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model

    # --- Asynchronous Methods (for FastAPI) ---

    async def get(self, db: AsyncSession, id: Any) -> Optional[T]:
        """
        Fetch a single record by primary key asynchronously.
        """
        return await db.get(self.model, id)

    async def get_all(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[T]:
        """
        Fetch all records with optional pagination asynchronously.
        """
        stmt = select(self.model).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, obj: T) -> T:
        """
        Add a new record to the database asynchronously.
        """
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def update(self, db: AsyncSession, db_obj: T, update_data: Dict[str, Any]) -> T:
        """
        Update an existing record fields asynchronously.
        """
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, id: Any) -> bool:
        """
        Delete a record by primary key asynchronously.
        """
        db_obj = await self.get(db, id)
        if not db_obj:
            return False
        await db.delete(db_obj)
        await db.commit()
        return True

    # --- Synchronous Methods (for Celery, Tests, CLI) ---

    def get_sync(self, db: Session, id: Any) -> Optional[T]:
        """
        Fetch a single record by primary key synchronously.
        """
        return db.get(self.model, id)

    def get_all_sync(self, db: Session, skip: int = 0, limit: int = 100) -> List[T]:
        """
        Fetch all records with optional pagination synchronously.
        """
        return db.query(self.model).offset(skip).limit(limit).all()

    def create_sync(self, db: Session, obj: T) -> T:
        """
        Add a new record to the database synchronously.
        """
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update_sync(self, db: Session, db_obj: T, update_data: Dict[str, Any]) -> T:
        """
        Update an existing record fields synchronously.
        """
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete_sync(self, db: Session, id: Any) -> bool:
        """
        Delete a record by primary key synchronously.
        """
        db_obj = self.get_sync(db, id)
        if not db_obj:
            return False
        db.delete(db_obj)
        db.commit()
        return True
