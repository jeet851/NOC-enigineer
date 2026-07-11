from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from database.base import Base
from datetime import datetime
from typing import Optional

class VaultSecret(Base):
    __tablename__ = "vault_secrets"

    name: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    secret_type: Mapped[str] = mapped_column(String, nullable=False, index=True)  # e.g., SSH Key, API Token
    encrypted_value: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_rotated: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
