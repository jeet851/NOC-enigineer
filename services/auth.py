import os
import bcrypt
import secrets
import re
from datetime import datetime, timedelta
from typing import List, Optional, Any
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

from api.config import settings
from models.token import UserRefreshToken

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def validate_password_strength(password: str) -> tuple[bool, List[str]]:
    """
    Validates a password against standard enterprise complexity rules.
    Returns (is_strong: bool, errors: list[str])
    """
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one numerical digit.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("Password must contain at least one special character.")
        
    return len(errors) == 0, errors

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token expired or invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Refresh Token Service Operations
def generate_refresh_token() -> str:
    return secrets.token_hex(32)

# --- Synchronous Methods (for Celery & Legacy Callers) ---

def save_refresh_token(db: Session, user_id: int, token: str, expires_days: int = 7):
    expires_at = datetime.utcnow() + timedelta(days=expires_days)
    db_token = UserRefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        is_revoked=False
    )
    db.add(db_token)
    db.commit()

def verify_refresh_token(db: Session, token: str) -> Optional[UserRefreshToken]:
    db_token = db.query(UserRefreshToken).filter(
        UserRefreshToken.token == token,
        UserRefreshToken.is_revoked == False
    ).first()
    
    if db_token and db_token.expires_at > datetime.utcnow():
        return db_token
    return None

def revoke_refresh_token(db: Session, token: str) -> bool:
    db_token = db.query(UserRefreshToken).filter(UserRefreshToken.token == token).first()
    if db_token:
        db_token.is_revoked = True
        db.commit()
        return True
    return False

# --- Asynchronous Methods (for FastAPI / AsyncSession) ---

async def save_refresh_token_async(db: AsyncSession, user_id: int, token: str, expires_days: int = 7):
    expires_at = datetime.utcnow() + timedelta(days=expires_days)
    db_token = UserRefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        is_revoked=False
    )
    db.add(db_token)
    await db.commit()

async def verify_refresh_token_async(db: AsyncSession, token: str) -> Optional[UserRefreshToken]:
    stmt = select(UserRefreshToken).where(
        UserRefreshToken.token == token,
        UserRefreshToken.is_revoked == False
    )
    result = await db.execute(stmt)
    db_token = result.scalars().first()
    
    if db_token and db_token.expires_at > datetime.utcnow():
        return db_token
    return None

async def revoke_refresh_token_async(db: AsyncSession, token: str) -> bool:
    stmt = select(UserRefreshToken).where(UserRefreshToken.token == token)
    result = await db.execute(stmt)
    db_token = result.scalars().first()
    if db_token:
        db_token.is_revoked = True
        await db.commit()
        return True
    return False

class RoleChecker:
    """
    Dependency to enforce Role Based Access Control (RBAC) on route endpoints.
    """
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, payload: dict = Depends(decode_token)):
        user_role = payload.get("role")
        if not user_role or user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission Denied: User role '{user_role}' lacks required permissions."
            )
        return payload

# TOTP Security Logic (RFC 6238)
import hmac
import hashlib
import time
import struct
import base64

def generate_totp_secret() -> str:
    """Generates a random 16-character base32 secret key."""
    import secrets
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    return "".join(secrets.choice(chars) for _ in range(16))

def get_totp_token(secret: str) -> str:
    """Calculates the current 6-digit TOTP code for a given secret."""
    secret = secret.strip().replace(" ", "").upper()
    missing_padding = len(secret) % 8
    if missing_padding:
        secret += '=' * (8 - missing_padding)
    key = base64.b32decode(secret)
    t = int(time.time() / 30)
    msg = struct.pack(">Q", t)
    hmac_hash = hmac.new(key, msg, hashlib.sha1).digest()
    offset = hmac_hash[-1] & 0x0F
    code = ((hmac_hash[offset] & 0x7F) << 24 |
            (hmac_hash[offset+1] & 0xFF) << 16 |
            (hmac_hash[offset+2] & 0xFF) << 8 |
            (hmac_hash[offset+3] & 0xFF))
    code = code % 1000000
    return f"{code:06d}"

def verify_totp_token(secret: str, code: str) -> bool:
    """Verifies a 6-digit TOTP code with time drift window (+/- 30 seconds)."""
    if not secret or not code:
        return False
    code = code.strip()
    try:
        secret = secret.strip().replace(" ", "").upper()
        missing_padding = len(secret) % 8
        if missing_padding:
            secret += '=' * (8 - missing_padding)
        key = base64.b32decode(secret)
    except Exception:
        return False
        
    t_now = int(time.time() / 30)
    # Check t-1, t, t+1
    for offset_t in [-1, 0, 1]:
        t = t_now + offset_t
        msg = struct.pack(">Q", t)
        hmac_hash = hmac.new(key, msg, hashlib.sha1).digest()
        offset = hmac_hash[-1] & 0x0F
        val = ((hmac_hash[offset] & 0x7F) << 24 |
               (hmac_hash[offset+1] & 0xFF) << 16 |
               (hmac_hash[offset+2] & 0xFF) << 8 |
               (hmac_hash[offset+3] & 0xFF))
        val = val % 1000000
        if f"{val:06d}" == code:
            return True
    return False
