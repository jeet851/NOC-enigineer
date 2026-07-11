from sqlalchemy.orm import Session
from models.telemetry import TelemetryLog
from datetime import datetime
from typing import List

class TelemetryService:
    @staticmethod
    def log_telemetry(
        db: Session,
        device_name: str,
        ping_rtt: float,
        min_rtt: float,
        max_rtt: float,
        packet_loss: float,
        jitter: float,
        cpu: int,
        ram: int,
        interface_errors: int,
        status: str
    ) -> TelemetryLog:
        log = TelemetryLog(
            device_name=device_name,
            ping_rtt=ping_rtt,
            min_rtt=min_rtt,
            max_rtt=max_rtt,
            packet_loss=packet_loss,
            jitter=jitter,
            cpu=cpu,
            ram=ram,
            interface_errors=interface_errors,
            status=status,
            timestamp=datetime.utcnow()
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def get_latest_telemetry(db: Session, device_name: str, limit: int = 50) -> List[TelemetryLog]:
        return db.query(TelemetryLog)\
            .filter(TelemetryLog.device_name == device_name)\
            .order_by(TelemetryLog.timestamp.desc())\
            .limit(limit)\
            .all()
