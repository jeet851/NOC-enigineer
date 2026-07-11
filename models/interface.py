from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base
from typing import Optional

class Interface(Base):
    __tablename__ = "interfaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_name: Mapped[str] = mapped_column(String, ForeignKey("devices.name", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    mac_address: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="up")  # up, down, admin_down
    speed: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)         # e.g., 1Gbps, 10Gbps
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Relationships
    device: Mapped["Device"] = relationship("Device", back_populates="interfaces")
