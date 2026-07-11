from sqlalchemy import Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base
from datetime import datetime
from typing import Optional


class IncidentTimeline(Base):
    __tablename__ = "incident_timelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    status_from: Mapped[str] = mapped_column(String(50), nullable=False)
    status_to: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="timeline_events")
