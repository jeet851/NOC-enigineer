from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base
from typing import Optional

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # Keep string for backwards compat (Admin, Manager, Senior Engineer, Network Engineer, Guest)
    name: Mapped[str] = mapped_column(String, nullable=False)
    totp_secret: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # RBAC additions
    role_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    role_relation: Mapped[Optional["Role"]] = relationship("Role")
