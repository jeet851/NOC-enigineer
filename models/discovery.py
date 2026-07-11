from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from database.base import Base
from datetime import datetime
from typing import Optional

class DiscoveryLog(Base):
    __tablename__ = "discovery_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    subnet: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)  # Running, Completed, Failed
    devices_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    log_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
