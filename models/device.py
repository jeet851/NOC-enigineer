from sqlalchemy import Column, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base
from typing import Optional, List

class Device(Base):
    __tablename__ = "devices"

    name: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    ip: Mapped[str] = mapped_column(String, nullable=False)
    vendor: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # Healthy, Warning, Critical
    role: Mapped[str] = mapped_column(String, nullable=False)
    site: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    interfaces: Mapped[List["Interface"]] = relationship("Interface", back_populates="device", cascade="all, delete-orphan")
