from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from database.base import Base
from datetime import datetime
from typing import Optional

class Alarm(Base):
    __tablename__ = "alarms"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String, nullable=False, index=True)  # Device IP / host
    metric: Mapped[str] = mapped_column(String, nullable=False)              # e.g., CPU, VPN status
    value: Mapped[str] = mapped_column(String, nullable=False)               # e.g., 94%, Offline
    severity: Mapped[str] = mapped_column(String, nullable=False, index=True) # Warning, Critical
    time_display: Mapped[str] = mapped_column(String, nullable=False)        # e.g., "5m ago"
    status: Mapped[str] = mapped_column(String, nullable=False, default="Active", index=True)  # Active, Resolved
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
