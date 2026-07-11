from sqlalchemy import Integer, String, DateTime, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from database.base import Base
from datetime import datetime
from typing import Optional


class BackgroundTask(Base):
    __tablename__ = "background_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="Pending", nullable=False, index=True) # Pending, Running, Finished, Failed
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
