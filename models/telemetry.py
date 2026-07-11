from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.base import Base
from datetime import datetime
from typing import Optional

class TelemetryLog(Base):
    __tablename__ = "telemetry_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    device_name: Mapped[str] = mapped_column(String, ForeignKey("devices.name", ondelete="CASCADE"), nullable=False, index=True)
    ping_rtt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_rtt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_rtt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    packet_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    jitter: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpu: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ram: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    interface_errors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Extra monitoring metrics
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    disk_utilization: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Telemetry updates
    bw_in: Mapped[Optional[float]] = mapped_column(Float, nullable=True)          # Incoming bandwidth Mbps
    bw_out: Mapped[Optional[float]] = mapped_column(Float, nullable=True)         # Outgoing bandwidth Mbps
    vpn_tunnels_up: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # Count of active tunnels
    bgp_peer_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # BGP session status
    ospf_neighbor_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fw_sessions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    device: Mapped["Device"] = relationship("Device")
