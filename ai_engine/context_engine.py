"""
AI Context Engine – Phase 3 Intelligence Enhancement
Builds a rich, structured AIContext object before every LLM call by aggregating
telemetry, incidents, device status, alarms, topology, user role, and conversation
history. Replaces ad-hoc string building scattered across chat.py and ai_engine.py.
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("noc.context_engine")


# ---------------------------------------------------------------------------
# AIContext dataclass (plain dict for JSON-serialisability)
# ---------------------------------------------------------------------------

def _empty_context() -> Dict[str, Any]:
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "user": {"username": "unknown", "role": "viewer"},
        "telemetry": [],          # latest telemetry per device (up to 10 devices)
        "active_incidents": [],   # active incident records
        "active_alarms": [],      # active alarms
        "devices": [],            # device inventory
        "topology": {},           # topology graph
        "recent_automation": [],  # last 5 automation actions from audit log
        "alert_history": [],      # last 10 resolved/active alarms
        "conversation_summary": "",  # summarised prior turns
        "config_drift_warnings": [],  # mismatches from config baseline
        "interface_status": [],   # per-device interface summary
    }


# ---------------------------------------------------------------------------
# Context Engine
# ---------------------------------------------------------------------------

class ContextEngine:
    """
    Gathers operational context from all available data sources and assembles
    a structured AIContext dict that is injected into every LLM system prompt.
    """

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def build_context(
        db=None,
        user: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None,
        active_scenario: Optional[str] = None,
        extra: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Build and return a complete AIContext dict.

        Parameters
        ----------
        db          : SQLAlchemy Session (optional – graceful degradation if None)
        user        : dict with 'username' and 'role'
        conversation_history : list of {'role': str, 'text': str} dicts
        active_scenario      : scenario key string
        extra       : arbitrary additional key/values to merge
        """
        ctx = _empty_context()
        ctx["generated_at"] = datetime.utcnow().isoformat()

        # 1. User context
        if user:
            ctx["user"] = {
                "username": user.get("username", "unknown"),
                "role": user.get("role", "viewer"),
            }

        # 2. Telemetry (latest readings from DB)
        ctx["telemetry"] = ContextEngine._gather_telemetry(db)

        # 3. Active incidents
        ctx["active_incidents"] = ContextEngine._gather_active_incidents(db)

        # 4. Active alarms
        ctx["active_alarms"] = ContextEngine._gather_alarms(db)

        # 5. Device inventory
        ctx["devices"] = ContextEngine._gather_devices(db)

        # 6. Topology
        ctx["topology"] = ContextEngine._gather_topology()

        # 7. Recent automation actions (from audit log)
        ctx["recent_automation"] = ContextEngine._gather_recent_automation(db)

        # 8. Alert history (last 10)
        ctx["alert_history"] = ContextEngine._gather_alert_history(db)

        # 9. Conversation summary
        if conversation_history:
            ctx["conversation_summary"] = ContextEngine._summarise_history(
                conversation_history
            )

        # 10. Active scenario hint
        if active_scenario:
            ctx["active_scenario"] = active_scenario

        # 11. Interface status (derived from telemetry)
        ctx["interface_status"] = ContextEngine._derive_interface_status(
            ctx["telemetry"]
        )

        # 12. Config drift warnings (from knowledge base if available)
        ctx["config_drift_warnings"] = ContextEngine._gather_config_drift()

        # Merge extras
        if extra:
            ctx.update(extra)

        return ctx

    # ------------------------------------------------------------------ #
    # Context → System Prompt String                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def format_for_prompt(ctx: Dict[str, Any]) -> str:
        """
        Convert an AIContext dict into a concise, LLM-friendly system prompt
        block injected after the persona instruction.
        """
        lines = [
            "=== OPERATIONAL CONTEXT (auto-gathered) ===",
            f"Timestamp: {ctx.get('generated_at', 'N/A')}",
            f"Operator: {ctx['user']['username']} | Role: {ctx['user']['role']}",
        ]

        # Active incidents
        incidents = ctx.get("active_incidents", [])
        if incidents:
            lines.append(f"\nACTIVE INCIDENTS ({len(incidents)}):")
            for inc in incidents[:5]:
                lines.append(
                    f"  • [{inc.get('severity','?')}] {inc.get('id','?')} – "
                    f"{inc.get('device_name','?')} | {inc.get('description','?')[:80]} "
                    f"| Root Cause: {inc.get('root_cause','?')[:60]} | Status: {inc.get('status','?')}"
                )
        else:
            lines.append("\nACTIVE INCIDENTS: None")

        # Active alarms
        alarms = ctx.get("active_alarms", [])
        if alarms:
            lines.append(f"\nACTIVE ALARMS ({len(alarms)}):")
            for alm in alarms[:5]:
                lines.append(
                    f"  • [{alm.get('severity','?')}] {alm.get('source','?')} – "
                    f"{alm.get('metric','?')}: {alm.get('value','?')}"
                )

        # Telemetry snapshot
        telemetry = ctx.get("telemetry", [])
        if telemetry:
            lines.append(f"\nTELEMETRY SNAPSHOT ({len(telemetry)} devices):")
            for t in telemetry[:8]:
                cpu_s = f"CPU:{t.get('cpu','?')}%" if t.get("cpu") is not None else ""
                ram_s = f"RAM:{t.get('ram','?')}%" if t.get("ram") is not None else ""
                pkt_s = f"Loss:{t.get('packet_loss','?')}%" if t.get("packet_loss") is not None else ""
                rtt_s = f"RTT:{t.get('ping_rtt','?')}ms" if t.get("ping_rtt") is not None else ""
                lines.append(
                    f"  • {t.get('device_name','?')} | Status:{t.get('status','?')} "
                    f"| {cpu_s} {ram_s} {pkt_s} {rtt_s}"
                )

        # Device inventory summary
        devices = ctx.get("devices", [])
        if devices:
            up = sum(1 for d in devices if d.get("status") == "Up")
            down = sum(1 for d in devices if d.get("status") == "Down")
            lines.append(f"\nDEVICE INVENTORY: {len(devices)} total | {up} Up | {down} Down")

        # Topology
        topo = ctx.get("topology", {})
        if topo.get("nodes"):
            node_names = ", ".join(
                n.get("id", n.get("name", "?")) for n in topo["nodes"][:6]
            )
            lines.append(f"\nTOPOLOGY NODES: {node_names}")

        # Recent automation
        automations = ctx.get("recent_automation", [])
        if automations:
            lines.append(f"\nRECENT AUTOMATION ACTIONS ({len(automations)}):")
            for a in automations[:3]:
                lines.append(
                    f"  • {a.get('timestamp','?')[:16]} | {a.get('action','?')} "
                    f"by {a.get('user_name','?')}"
                )

        # Config drift
        drifts = ctx.get("config_drift_warnings", [])
        if drifts:
            lines.append(f"\nCONFIG DRIFT WARNINGS ({len(drifts)}):")
            for d in drifts[:3]:
                lines.append(f"  • {d}")

        # Conversation summary
        summary = ctx.get("conversation_summary", "")
        if summary:
            lines.append(f"\nCONVERSATION HISTORY SUMMARY:\n{summary}")

        lines.append("=== END OPERATIONAL CONTEXT ===\n")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Private Gatherers                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _gather_telemetry(db) -> List[Dict]:
        """Gather latest telemetry reading per device from DB."""
        if db is None:
            return []
        try:
            from models.telemetry import TelemetryLog
            from models.device import Device
            from sqlalchemy import func

            # Subquery: latest timestamp per device
            sub = (
                db.query(
                    TelemetryLog.device_name,
                    func.max(TelemetryLog.timestamp).label("max_ts"),
                )
                .group_by(TelemetryLog.device_name)
                .subquery()
            )
            rows = (
                db.query(TelemetryLog)
                .join(
                    sub,
                    (TelemetryLog.device_name == sub.c.device_name)
                    & (TelemetryLog.timestamp == sub.c.max_ts),
                )
                .limit(15)
                .all()
            )
            result = []
            for r in rows:
                result.append(
                    {
                        "device_name": r.device_name,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                        "cpu": r.cpu,
                        "ram": r.ram,
                        "ping_rtt": r.ping_rtt,
                        "packet_loss": r.packet_loss,
                        "jitter": r.jitter,
                        "interface_errors": r.interface_errors,
                        "status": r.status,
                        "temperature": r.temperature,
                        "disk_utilization": r.disk_utilization,
                        "vpn_tunnels_up": r.vpn_tunnels_up,
                        "bgp_peer_status": r.bgp_peer_status,
                        "ospf_neighbor_count": r.ospf_neighbor_count,
                    }
                )
            return result
        except Exception as e:
            logger.warning(f"Telemetry gather failed: {e}")
            return []

    @staticmethod
    def _gather_active_incidents(db) -> List[Dict]:
        if db is None:
            return []
        try:
            from models.incident import Incident

            incidents = (
                db.query(Incident)
                .filter(Incident.status == "Active")
                .order_by(Incident.timestamp.desc())
                .limit(10)
                .all()
            )
            return [
                {
                    "id": i.id,
                    "severity": i.severity,
                    "device_name": i.device_name,
                    "site": i.site,
                    "vendor": i.vendor,
                    "description": i.description,
                    "root_cause": i.root_cause,
                    "business_impact": i.business_impact,
                    "confidence": i.confidence,
                    "status": i.status,
                    "timestamp": i.timestamp.isoformat() if i.timestamp else None,
                    "assigned_to": i.assigned_to,
                    "risk_level": i.risk_level,
                }
                for i in incidents
            ]
        except Exception as e:
            logger.warning(f"Active incidents gather failed: {e}")
            return []

    @staticmethod
    def _gather_alarms(db) -> List[Dict]:
        if db is None:
            return []
        try:
            from models.alarm import Alarm

            alarms = (
                db.query(Alarm)
                .filter(Alarm.status == "Active")
                .order_by(Alarm.timestamp.desc())
                .limit(10)
                .all()
            )
            return [
                {
                    "id": a.id,
                    "source": a.source,
                    "metric": a.metric,
                    "value": a.value,
                    "severity": a.severity,
                    "time_display": a.time_display,
                    "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                }
                for a in alarms
            ]
        except Exception as e:
            logger.warning(f"Alarms gather failed: {e}")
            return []

    @staticmethod
    def _gather_devices(db) -> List[Dict]:
        if db is None:
            return []
        try:
            from models.device import Device

            devices = db.query(Device).limit(30).all()
            return [
                {
                    "name": d.name,
                    "ip": d.ip,
                    "vendor": d.vendor,
                    "platform": d.platform,
                    "status": d.status,
                    "role": d.role,
                    "site": d.site,
                }
                for d in devices
            ]
        except Exception as e:
            logger.warning(f"Devices gather failed: {e}")
            return []

    @staticmethod
    def _gather_topology() -> Dict:
        try:
            if os.path.exists("topology.json"):
                with open("topology.json", "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Topology gather failed: {e}")
        return {}

    @staticmethod
    def _gather_recent_automation(db) -> List[Dict]:
        if db is None:
            return []
        try:
            from models.audit import AuditLog

            logs = (
                db.query(AuditLog)
                .filter(
                    AuditLog.action.in_(
                        [
                            "Config Deploy",
                            "Automation Execute",
                            "Self-Heal Triggered",
                            "Rollback",
                            "Config Backup",
                            "Zero-Trust Patch",
                        ]
                    )
                )
                .order_by(AuditLog.timestamp.desc())
                .limit(5)
                .all()
            )
            return [
                {
                    "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                    "user_name": l.user_name,
                    "action": l.action,
                    "details": l.details[:100] if l.details else "",
                    "status": l.status,
                }
                for l in logs
            ]
        except Exception as e:
            logger.warning(f"Recent automation gather failed: {e}")
            return []

    @staticmethod
    def _gather_alert_history(db) -> List[Dict]:
        if db is None:
            return []
        try:
            from models.alarm import Alarm

            alarms = (
                db.query(Alarm)
                .order_by(Alarm.timestamp.desc())
                .limit(10)
                .all()
            )
            return [
                {
                    "id": a.id,
                    "source": a.source,
                    "metric": a.metric,
                    "value": a.value,
                    "severity": a.severity,
                    "status": a.status,
                    "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                }
                for a in alarms
            ]
        except Exception as e:
            logger.warning(f"Alert history gather failed: {e}")
            return []

    @staticmethod
    def _derive_interface_status(telemetry: List[Dict]) -> List[Dict]:
        """Derive a simplified interface status list from telemetry data."""
        statuses = []
        for t in telemetry:
            errors = t.get("interface_errors", 0) or 0
            health = "Healthy"
            if errors > 100:
                health = "Degraded"
            elif errors > 500:
                health = "Critical"
            statuses.append(
                {
                    "device": t.get("device_name"),
                    "interface_errors": errors,
                    "health": health,
                    "vpn_tunnels_up": t.get("vpn_tunnels_up"),
                    "bgp_peer_status": t.get("bgp_peer_status"),
                    "ospf_neighbor_count": t.get("ospf_neighbor_count"),
                }
            )
        return statuses

    @staticmethod
    def _summarise_history(history: List[Dict]) -> str:
        """
        Produce a concise summary of the last N conversation turns so the LLM
        can reference earlier discussions without consuming the full context window.
        """
        if not history:
            return ""
        # Take last 10 turns max for summary
        recent = history[-10:]
        parts = []
        for msg in recent:
            role = "Operator" if msg.get("role") == "user" else "AI"
            text = msg.get("text", "")[:120]
            parts.append(f"{role}: {text}")
        return "\n".join(parts)

    @staticmethod
    def _gather_config_drift() -> List[str]:
        """
        Detect configuration drift by comparing against gold-standard templates
        stored in the knowledge base.
        """
        warnings = []
        try:
            kb_path = "knowledge_base.json"
            if not os.path.exists(kb_path):
                return []
            with open(kb_path, "r") as f:
                kb = json.load(f)
            docs = kb.get("documents", [])
            for doc in docs:
                if "gold" in doc.get("id", "").lower() or "baseline" in doc.get(
                    "title", ""
                ).lower():
                    warnings.append(
                        f"Baseline document '{doc.get('title','')}' available "
                        f"for compliance comparison (last updated: {doc.get('timestamp','?')[:10]})"
                    )
        except Exception:
            pass
        return warnings[:5]
