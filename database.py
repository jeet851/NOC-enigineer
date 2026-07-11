import os
from datetime import datetime
from database.session import SessionLocal, engine
from database.base import Base
from models.device import Device
from models.telemetry import TelemetryLog
from models.audit import AuditLog
from models.alarm import Alarm
from models.vault import VaultSecret

def db_init():
    """
    Compatibility layer for database initialization. Seeds default configurations.
    """
    from database.seed import seed_db
    seed_db()

def get_all_devices():
    db = SessionLocal()
    try:
        devices = db.query(Device).all()
        return [
            {
                "name": d.name,
                "ip": d.ip,
                "vendor": d.vendor,
                "platform": d.platform,
                "status": d.status,
                "role": d.role,
                "site": d.site,
                "description": d.description
            } for d in devices
        ]
    finally:
        db.close()

def update_device_status(name, status):
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.name == name).first()
        if device:
            device.status = status
            db.commit()
    finally:
        db.close()

def log_telemetry(device_name, ping_rtt, min_rtt, max_rtt, packet_loss, jitter, cpu, ram, interface_errors, status):
    db = SessionLocal()
    try:
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
    finally:
        db.close()

def get_latest_telemetry(device_name, limit=50):
    db = SessionLocal()
    try:
        logs = db.query(TelemetryLog)\
            .filter(TelemetryLog.device_name == device_name)\
            .order_by(TelemetryLog.timestamp.desc())\
            .limit(limit)\
            .all()
        return [
            {
                "id": l.id,
                "timestamp": l.timestamp.isoformat(),
                "device_name": l.device_name,
                "ping_rtt": l.ping_rtt,
                "min_rtt": l.min_rtt,
                "max_rtt": l.max_rtt,
                "packet_loss": l.packet_loss,
                "jitter": l.jitter,
                "cpu": l.cpu,
                "ram": l.ram,
                "interface_errors": l.interface_errors,
                "status": l.status
            } for l in logs
        ]
    finally:
        db.close()

def add_db_audit_event(user, role, action, ip, details, status="Success", changes="N/A", approvals="N/A", rollback="N/A"):
    db = SessionLocal()
    try:
        log = AuditLog(
            timestamp=datetime.utcnow(),
            user_name=user,
            role=role,
            ip=ip,
            action=action,
            details=details,
            status=status,
            changes=changes,
            approvals=approvals,
            rollback=rollback
        )
        db.add(log)
        db.commit()
    finally:
        db.close()

def get_db_audit_logs(limit=100):
    db = SessionLocal()
    try:
        logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
        return [
            {
                "id": l.id,
                "timestamp": l.timestamp.isoformat(),
                "user_name": l.user_name,
                "user": l.user_name,
                "role": l.role,
                "ip": l.ip,
                "action": l.action,
                "details": l.details,
                "status": l.status,
                "changes": l.changes,
                "approvals": l.approvals,
                "rollback": l.rollback
            } for l in logs
        ]
    finally:
        db.close()

def get_db_alarms():
    db = SessionLocal()
    try:
        alarms = db.query(Alarm).filter(Alarm.status == "Active").all()
        return [
            {
                "id": a.id,
                "timestamp": a.timestamp.isoformat(),
                "source": a.source,
                "metric": a.metric,
                "value": a.value,
                "severity": a.severity,
                "time_display": a.time_display,
                "status": a.status
            } for a in alarms
        ]
    finally:
        db.close()

def add_db_alarm(alarm_id, source, metric, value, severity, time_display="Just now"):
    db = SessionLocal()
    try:
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
    finally:
        db.close()

def resolve_db_alarm(alarm_id):
    db = SessionLocal()
    try:
        alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
        if alarm:
            alarm.status = "Resolved"
            db.commit()
    finally:
        db.close()

def get_db_secrets():
    db = SessionLocal()
    try:
        secrets = db.query(VaultSecret).all()
        return {s.name: {"type": s.secret_type, "value": s.encrypted_value} for s in secrets}
    finally:
        db.close()

def save_db_secret(name, secret_type, encrypted_value):
    db = SessionLocal()
    try:
        secret = db.query(VaultSecret).filter(VaultSecret.name == name).first()
        if secret:
            secret.secret_type = secret_type
            secret.encrypted_value = encrypted_value
        else:
            secret = VaultSecret(name=name, secret_type=secret_type, encrypted_value=encrypted_value)
            db.add(secret)
        db.commit()
    finally:
        db.close()

def get_db_secret(name):
    db = SessionLocal()
    try:
        secret = db.query(VaultSecret).filter(VaultSecret.name == name).first()
        if secret:
            return {
                "name": secret.name,
                "secret_type": secret.secret_type,
                "encrypted_value": secret.encrypted_value
            }
        return None
    finally:
        db.close()

def delete_db_secret(name):
    db = SessionLocal()
    try:
        secret = db.query(VaultSecret).filter(VaultSecret.name == name).first()
        if secret:
            db.delete(secret)
            db.commit()
            return True
        return False
    finally:
        db.close()

# Auto-initialize compatibility layer tables
db_init()
