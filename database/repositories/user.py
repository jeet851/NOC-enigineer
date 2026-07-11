from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select
from models.user import User
from database.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        """
        Fetch a user by their username (case-insensitive lookup) asynchronously.
        """
        stmt = select(User).where(User.username == username.strip().lower())
        result = await db.execute(stmt)
        return result.scalars().first()

    def get_by_username_sync(self, db: Session, username: str) -> Optional[User]:
        """
        Fetch a user by their username (case-insensitive lookup) synchronously.
        """
        return db.query(User).filter(User.username == username.strip().lower()).first()
