from sqlalchemy import Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database.base import Base
from datetime import datetime
from typing import Optional


class ComplianceReport(Base):
    __tablename__ = "compliance_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False) # RCA, MOP, SOP
    incident_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generated_by: Mapped[str] = mapped_column(String(100), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
