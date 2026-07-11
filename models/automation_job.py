from sqlalchemy import Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from database.base import Base
from datetime import datetime
from typing import Optional


class AutomationJob(Base):
    __tablename__ = "automation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. "Ansible", "Netmiko", "NAPALM"
    device_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="Pending", nullable=False, index=True) # Pending, Running, Success, Failed
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    output_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(100), nullable=False)
