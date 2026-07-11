from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base
from datetime import datetime
from typing import Optional

class ConfigurationBackup(Base):
    __tablename__ = "configuration_backups"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    device_name: Mapped[str] = mapped_column(String, ForeignKey("devices.name", ondelete="CASCADE"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    running_config: Mapped[str] = mapped_column(Text, nullable=False)
    startup_config: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    device: Mapped["Device"] = relationship("Device")
