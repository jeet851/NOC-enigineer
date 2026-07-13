"""
AI Recommendations Engine – Phase 3 Intelligence Enhancement
Generates proactive, telemetry-driven recommendations that feed the dashboard
AI panel. Analyses live telemetry trends and correlates with active incidents
to surface intelligent, actionable recommendations automatically.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("noc.recommendations")


# ---------------------------------------------------------------------------
# Recommendation schema
# ---------------------------------------------------------------------------

def _make_recommendation(
    rec_type: str,
    device: str,
    severity: str,
    message: str,
    action: str,
    confidence: int,
    evidence: Optional[str] = None,
    category: str = "Operations",
) -> Dict[str, Any]:
    return {
        "id": f"REC-{rec_type.upper()}-{device.replace('-','')[:8]}-{datetime.utcnow().strftime('%H%M%S')}",
        "type": rec_type,
        "device": device,
        "severity": severity,        # info | warning | critical
        "category": category,
        "message": message,
        "action": action,
        "confidence": confidence,
        "evidence": evidence or "",
        "generated_at": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

CPU_WARNING = 75
CPU_CRITICAL = 90
RAM_WARNING = 80
RAM_CRITICAL = 90
PACKET_LOSS_WARNING = 1.0
PACKET_LOSS_CRITICAL = 5.0
JITTER_WARNING = 20.0
INTERFACE_ERROR_WARNING = 50
DISK_WARNING = 80.0
TEMP_WARNING = 60.0


# ---------------------------------------------------------------------------
# Recommendations Engine
# ---------------------------------------------------------------------------

class RecommendationsEngine:
    """
    Analyses telemetry, incident data, and alarm trends to produce proactive
    AIOps recommendations for the dashboard panel and Slack alerts.
    """

    @staticmethod
    def generate(
        telemetry: Optional[List[Dict]] = None,
        active_incidents: Optional[List[Dict]] = None,
        active_alarms: Optional[List[Dict]] = None,
        devices: Optional[List[Dict]] = None,
        db=None,
    ) -> Dict[str, Any]:
        """
        Generate the full set of proactive recommendations.

        Returns
        -------
        {
            "recommendations": [...],
            "summary": "...",
            "generated_at": "...",
            "total_count": int,
            "critical_count": int,
            "warning_count": int,
        }
        """
        recs: List[Dict] = []

        # 1. Telemetry-based recommendations
        if telemetry:
            recs.extend(RecommendationsEngine._analyse_cpu(telemetry))
            recs.extend(RecommendationsEngine._analyse_memory(telemetry))
            recs.extend(RecommendationsEngine._analyse_packet_loss(telemetry))
            recs.extend(RecommendationsEngine._analyse_interface_errors(telemetry))
            recs.extend(RecommendationsEngine._analyse_thermal(telemetry))
            recs.extend(RecommendationsEngine._analyse_disk(telemetry))
            recs.extend(RecommendationsEngine._analyse_vpn_tunnels(telemetry))
            recs.extend(RecommendationsEngine._analyse_bgp(telemetry))

        # 2. Incident correlation
        if active_incidents:
            recs.extend(RecommendationsEngine._correlate_incidents(active_incidents))

        # 3. Device availability
        if devices:
            recs.extend(RecommendationsEngine._check_device_availability(devices))

        # 4. Alarm pattern analysis
        if active_alarms:
            recs.extend(RecommendationsEngine._analyse_alarm_patterns(active_alarms))

        # 5. Security recommendations
        recs.extend(RecommendationsEngine._security_recommendations(
            telemetry or [], active_alarms or []
        ))

        # 6. Compliance recommendations (from DB if available)
        if db is not None:
            recs.extend(RecommendationsEngine._compliance_recommendations(db))

        # Sort: critical first, then by confidence
        priority_order = {"critical": 0, "warning": 1, "info": 2}
        recs.sort(key=lambda r: (priority_order.get(r["severity"], 3), -r["confidence"]))

        # Deduplicate (same device + type)
        seen = set()
        unique_recs = []
        for r in recs:
            key = f"{r['type']}-{r['device']}"
            if key not in seen:
                seen.add(key)
                unique_recs.append(r)

        critical_count = sum(1 for r in unique_recs if r["severity"] == "critical")
        warning_count = sum(1 for r in unique_recs if r["severity"] == "warning")

        summary = RecommendationsEngine._build_summary(unique_recs, critical_count, warning_count)

        return {
            "recommendations": unique_recs[:20],  # cap at 20 for panel
            "summary": summary,
            "generated_at": datetime.utcnow().isoformat(),
            "total_count": len(unique_recs),
            "critical_count": critical_count,
            "warning_count": warning_count,
        }

    # ------------------------------------------------------------------
    # Telemetry Analysers
    # ------------------------------------------------------------------

    @staticmethod
    def _analyse_cpu(telemetry: List[Dict]) -> List[Dict]:
        recs = []
        for t in telemetry:
            cpu = t.get("cpu")
            if cpu is None:
                continue
            device = t.get("device_name", "Unknown")
            if cpu >= CPU_CRITICAL:
                recs.append(_make_recommendation(
                    rec_type="cpu_critical",
                    device=device,
                    severity="critical",
                    message=f"CPU utilization at {cpu}% — CRITICAL threshold exceeded.",
                    action="Run `show processes cpu sorted`. Identify and terminate rogue processes. Engage Linux/NOC Engineer immediately.",
                    confidence=95,
                    evidence=f"Current CPU: {cpu}% (threshold: {CPU_CRITICAL}%)",
                    category="Performance",
                ))
            elif cpu >= CPU_WARNING:
                recs.append(_make_recommendation(
                    rec_type="cpu_anomaly",
                    device=device,
                    severity="warning",
                    message=f"CPU trending at {cpu}% — approaching critical threshold.",
                    action="Monitor CPU trend. Identify top processes. Plan maintenance if sustained above 80% for >15 min.",
                    confidence=82,
                    evidence=f"Current CPU: {cpu}% (warning threshold: {CPU_WARNING}%)",
                    category="Performance",
                ))
        return recs

    @staticmethod
    def _analyse_memory(telemetry: List[Dict]) -> List[Dict]:
        recs = []
        for t in telemetry:
            ram = t.get("ram")
            if ram is None:
                continue
            device = t.get("device_name", "Unknown")
            if ram >= RAM_CRITICAL:
                recs.append(_make_recommendation(
                    rec_type="memory_critical",
                    device=device,
                    severity="critical",
                    message=f"Memory utilization at {ram}% — OOM risk imminent.",
                    action="Identify memory-consuming processes. Consider service restart during maintenance window. Increase swap if available.",
                    confidence=92,
                    evidence=f"Current RAM: {ram}% (critical threshold: {RAM_CRITICAL}%)",
                    category="Performance",
                ))
            elif ram >= RAM_WARNING:
                recs.append(_make_recommendation(
                    rec_type="memory_anomaly",
                    device=device,
                    severity="warning",
                    message=f"Memory utilization at {ram}% — elevated above normal baseline.",
                    action="Monitor memory trend. Review top memory consumers. Check for memory leak indicators.",
                    confidence=78,
                    evidence=f"Current RAM: {ram}% (warning threshold: {RAM_WARNING}%)",
                    category="Performance",
                ))
        return recs

    @staticmethod
    def _analyse_packet_loss(telemetry: List[Dict]) -> List[Dict]:
        recs = []
        for t in telemetry:
            loss = t.get("packet_loss")
            if loss is None:
                continue
            device = t.get("device_name", "Unknown")
            if loss >= PACKET_LOSS_CRITICAL:
                recs.append(_make_recommendation(
                    rec_type="packet_loss_critical",
                    device=device,
                    severity="critical",
                    message=f"Packet loss at {loss}% on {device} — severe TCP throughput degradation.",
                    action="Check physical layer: cables, SFPs, duplex settings. Review interface error counters. Engage Network Engineer.",
                    confidence=93,
                    evidence=f"Packet loss: {loss}% (threshold: {PACKET_LOSS_CRITICAL}%)",
                    category="Network Health",
                ))
            elif loss >= PACKET_LOSS_WARNING:
                recs.append(_make_recommendation(
                    rec_type="packet_loss_warning",
                    device=device,
                    severity="warning",
                    message=f"Packet loss detected at {loss}% — monitoring recommended.",
                    action="Review interface error counters and QoS policies. Check upstream congestion.",
                    confidence=80,
                    evidence=f"Packet loss: {loss}% (threshold: {PACKET_LOSS_WARNING}%)",
                    category="Network Health",
                ))
        return recs

    @staticmethod
    def _analyse_interface_errors(telemetry: List[Dict]) -> List[Dict]:
        recs = []
        for t in telemetry:
            errors = t.get("interface_errors")
            if errors is None:
                continue
            device = t.get("device_name", "Unknown")
            if errors > INTERFACE_ERROR_WARNING * 10:
                recs.append(_make_recommendation(
                    rec_type="interface_instability",
                    device=device,
                    severity="critical",
                    message=f"High interface error rate ({errors} errors) on {device} — instability detected.",
                    action="Inspect physical layer. Check `show interface` for CRC/input errors. Replace SFP or cable if indicated.",
                    confidence=88,
                    evidence=f"Interface errors: {errors} (threshold: {INTERFACE_ERROR_WARNING * 10})",
                    category="Network Health",
                ))
            elif errors > INTERFACE_ERROR_WARNING:
                recs.append(_make_recommendation(
                    rec_type="interface_errors",
                    device=device,
                    severity="warning",
                    message=f"Interface errors increasing ({errors} errors) on {device}.",
                    action="Monitor trend. Check interface statistics for CRC/collision patterns.",
                    confidence=70,
                    evidence=f"Interface errors: {errors}",
                    category="Network Health",
                ))
        return recs

    @staticmethod
    def _analyse_thermal(telemetry: List[Dict]) -> List[Dict]:
        recs = []
        for t in telemetry:
            temp = t.get("temperature")
            if temp is None:
                continue
            device = t.get("device_name", "Unknown")
            if temp >= TEMP_WARNING:
                recs.append(_make_recommendation(
                    rec_type="thermal_warning",
                    device=device,
                    severity="warning" if temp < 75 else "critical",
                    message=f"Device temperature at {temp}°C on {device} — thermal protection risk.",
                    action="Check fan status (`show env fan`). Verify datacenter cooling. Clear ventilation intakes.",
                    confidence=90,
                    evidence=f"Temperature: {temp}°C (warning threshold: {TEMP_WARNING}°C)",
                    category="Hardware",
                ))
        return recs

    @staticmethod
    def _analyse_disk(telemetry: List[Dict]) -> List[Dict]:
        recs = []
        for t in telemetry:
            disk = t.get("disk_utilization")
            if disk is None:
                continue
            device = t.get("device_name", "Unknown")
            if disk >= 90:
                recs.append(_make_recommendation(
                    rec_type="disk_critical",
                    device=device,
                    severity="critical",
                    message=f"Disk utilization at {disk}% on {device} — service writes will fail at 100%.",
                    action="Run log cleanup: `find /var/log -name '*.gz' -mtime +30 -delete`. Expand partition if necessary.",
                    confidence=95,
                    evidence=f"Disk: {disk}% utilized",
                    category="Storage",
                ))
            elif disk >= DISK_WARNING:
                recs.append(_make_recommendation(
                    rec_type="disk_warning",
                    device=device,
                    severity="warning",
                    message=f"Disk utilization at {disk}% on {device} — review and cleanup recommended.",
                    action="Review large directories with `du -sh /*`. Configure log rotation policy.",
                    confidence=85,
                    evidence=f"Disk: {disk}% utilized",
                    category="Storage",
                ))
        return recs

    @staticmethod
    def _analyse_vpn_tunnels(telemetry: List[Dict]) -> List[Dict]:
        recs = []
        for t in telemetry:
            tunnels = t.get("vpn_tunnels_up")
            if tunnels is None:
                continue
            device = t.get("device_name", "Unknown")
            if tunnels == 0:
                recs.append(_make_recommendation(
                    rec_type="vpn_down",
                    device=device,
                    severity="critical",
                    message=f"All VPN tunnels down on {device} — remote connectivity severed.",
                    action="Check IKE Phase 1/2 status (`show crypto isakmp sa`). Verify peer reachability and lifetime settings.",
                    confidence=97,
                    evidence=f"VPN tunnels active: {tunnels}",
                    category="Connectivity",
                ))
        return recs

    @staticmethod
    def _analyse_bgp(telemetry: List[Dict]) -> List[Dict]:
        recs = []
        for t in telemetry:
            bgp = t.get("bgp_peer_status")
            if not bgp:
                continue
            device = t.get("device_name", "Unknown")
            if "down" in str(bgp).lower() or bgp == "Idle":
                recs.append(_make_recommendation(
                    rec_type="bgp_session_down",
                    device=device,
                    severity="critical",
                    message=f"BGP peer session Down/Idle on {device} — WAN routing redundancy at risk.",
                    action="Check `show ip bgp summary`. Verify TCP 179 access, holdtimers, and MD5 authentication.",
                    confidence=94,
                    evidence=f"BGP peer status: {bgp}",
                    category="Routing",
                ))
        return recs

    @staticmethod
    def _correlate_incidents(incidents: List[Dict]) -> List[Dict]:
        recs = []
        for inc in incidents[:5]:
            severity = "warning" if inc.get("severity", "").lower() == "warning" else "critical"
            recs.append(_make_recommendation(
                rec_type="active_incident",
                device=inc.get("device_name", "Unknown"),
                severity=severity,
                message=f"Active incident {inc.get('id','?')}: {inc.get('description','?')[:80]}",
                action=f"Root Cause: {inc.get('root_cause','?')[:80]}. Run RCA for structured analysis.",
                confidence=98,
                evidence=f"Incident status: {inc.get('status','?')} | Confidence: {inc.get('confidence','?')}",
                category="Incident",
            ))
        return recs

    @staticmethod
    def _check_device_availability(devices: List[Dict]) -> List[Dict]:
        recs = []
        down_devices = [d for d in devices if d.get("status", "").lower() in ("down", "unreachable")]
        for device in down_devices[:5]:
            recs.append(_make_recommendation(
                rec_type="device_down",
                device=device.get("name", "Unknown"),
                severity="critical",
                message=f"Device {device.get('name','?')} ({device.get('role','?')}) is DOWN at {device.get('site','?')}.",
                action="Verify physical connectivity. Check management access. Escalate to on-site team if unreachable.",
                confidence=99,
                evidence=f"Status: {device.get('status','?')} | Vendor: {device.get('vendor','?')}",
                category="Availability",
            ))
        return recs

    @staticmethod
    def _analyse_alarm_patterns(alarms: List[Dict]) -> List[Dict]:
        recs = []
        # Check for repeated alarms on same device (alarm storm)
        device_alarm_count: Dict[str, int] = {}
        for a in alarms:
            src = a.get("source", "Unknown")
            device_alarm_count[src] = device_alarm_count.get(src, 0) + 1

        for device, count in device_alarm_count.items():
            if count >= 3:
                recs.append(_make_recommendation(
                    rec_type="alarm_storm",
                    device=device,
                    severity="warning",
                    message=f"Alarm storm detected: {count} simultaneous alarms on {device}.",
                    action="Investigate root cause triggering multiple alarms. May indicate cascading failure. Run diagnostic sweep.",
                    confidence=80,
                    evidence=f"Active alarm count for device: {count}",
                    category="Alarm Management",
                ))
        return recs

    @staticmethod
    def _security_recommendations(telemetry: List[Dict], alarms: List[Dict]) -> List[Dict]:
        recs = []
        # Check for security-related alarms
        for a in alarms:
            metric = a.get("metric", "").lower()
            if any(w in metric for w in ["brute", "attack", "intrusion", "ssh fail", "scan"]):
                recs.append(_make_recommendation(
                    rec_type="security_threat",
                    device=a.get("source", "Unknown"),
                    severity="critical",
                    message=f"Security threat detected: {a.get('metric','?')} — {a.get('value','?')}.",
                    action="Block source IP at edge firewall. Escalate to Security Analyst. Preserve logs for forensic analysis.",
                    confidence=92,
                    evidence=f"Alarm: {a.get('metric','?')} | Value: {a.get('value','?')} | Severity: {a.get('severity','?')}",
                    category="Security",
                ))
        return recs

    @staticmethod
    def _compliance_recommendations(db) -> List[Dict]:
        recs = []
        try:
            from models.audit import AuditLog
            from datetime import datetime, timedelta

            # Check if any audit events indicate failed compliance
            recent = (
                db.query(AuditLog)
                .filter(AuditLog.status == "Failed")
                .filter(AuditLog.timestamp >= datetime.utcnow() - timedelta(hours=24))
                .limit(5)
                .all()
            )
            for log in recent:
                recs.append(_make_recommendation(
                    rec_type="compliance_failure",
                    device=log.details[:40] if log.details else "System",
                    severity="warning",
                    message=f"Compliance event: Failed action '{log.action}' by {log.user_name}.",
                    action="Review audit log. Verify Zero-Trust policy enforcement. Check for unauthorized access attempts.",
                    confidence=75,
                    evidence=f"Audit: {log.action} | User: {log.user_name} | Time: {log.timestamp.isoformat()[:16] if log.timestamp else 'N/A'}",
                    category="Compliance",
                ))
        except Exception as e:
            logger.debug(f"Compliance check failed: {e}")
        return recs

    @staticmethod
    def _build_summary(recs: List[Dict], critical: int, warning: int) -> str:
        if critical > 0:
            return (
                f"⚠️ {critical} CRITICAL recommendation(s) require immediate attention. "
                f"Additionally {warning} warning(s) detected. Review all recommendations below."
            )
        elif warning > 0:
            return f"📋 {warning} advisory recommendation(s) identified. No critical issues active."
        else:
            return "✅ All systems nominal. No significant anomalies detected in current telemetry."
