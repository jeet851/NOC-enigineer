from sqlalchemy import Column, String, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column
from database.base import Base
from datetime import datetime
from typing import Optional

class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)  # e.g. INC-2026-0001
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String, nullable=False, index=True)  # Critical, Warning, Info
    device_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    site: Mapped[str] = mapped_column(String, nullable=False)
    vendor: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    business_impact: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "95%"
    root_cause: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="Active", index=True)  # Active, Resolved

    # AI Investigator Enriched Fields
    evidence: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    remediation_commands: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    verification_steps: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rollback_plan: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    repair_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    engineering_report: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
