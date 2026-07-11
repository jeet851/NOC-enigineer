from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base
from datetime import datetime
from typing import Optional

class AIAnalysisHistory(Base):
    __tablename__ = "ai_analysis_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    scenario: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    safety_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., Passed, Destructive Command Blocked
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")
