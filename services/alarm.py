from sqlalchemy.orm import Session
from models.alarm import Alarm
from datetime import datetime
from typing import List, Optional

class AlarmService:
    @staticmethod
    def get_active_alarms(db: Session) -> List[Alarm]:
        return db.query(Alarm).filter(Alarm.status == "Active").all()

    @staticmethod
    def add_alarm(
        db: Session,
        alarm_id: str,
        source: str,
        metric: str,
        value: str,
        severity: str,
        time_display: str = "Just now"
    ) -> Alarm:
        alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
        if alarm:
            alarm.source = source
            alarm.metric = metric
            alarm.value = value
            alarm.severity = severity
            alarm.time_display = time_display
            alarm.status = "Active"
            alarm.timestamp = datetime.utcnow()
        else:
            alarm = Alarm(
                id=alarm_id,
                source=source,
                metric=metric,
                value=value,
                severity=severity,
                time_display=time_display,
                status="Active",
                timestamp=datetime.utcnow()
            )
            db.add(alarm)
        db.commit()
        db.refresh(alarm)
        return alarm

    @staticmethod
    def resolve_alarm(db: Session, alarm_id: str) -> bool:
        alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
        if alarm:
            alarm.status = "Resolved"
            db.commit()
            return True
        return False
