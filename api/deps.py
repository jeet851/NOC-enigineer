from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from database.session import SessionLocal, AsyncSessionLocal
from database.repositories.user import UserRepository
from services.auth import decode_token
from typing import AsyncGenerator, Generator

# Standard OAuth2 bearer scheme pointing to login route
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

user_repo = UserRepository()

def get_db() -> Generator[Session, None, None]:
    """
    Dependency to yield synchronous database sessions. Used by legacy/sync logic.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to yield asynchronous database sessions. Used by async routers.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_db)
) -> dict:
    """
    Dependency that decodes the JWT bearer token, checks database user existence,
    and returns user claims context asynchronously.
    """
    payload = decode_token(token)
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Check user record in database via UserRepository
    user = await user_repo.get_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session user no longer exists in database.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return {
        "username": user.username,
        "role": user.role,
        "name": user.name
    }
