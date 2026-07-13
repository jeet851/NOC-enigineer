"""
Structured RCA Engine – Phase 3 Intelligence Enhancement
Replaces the simple template-based RCA with 8-step structured reasoning that
correlates telemetry, configuration history, logs, topology, and historical
incidents to produce ranked, confidence-scored Root Cause Analyses.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("noc.rca_engine")


# ---------------------------------------------------------------------------
# RCA Schema
# ---------------------------------------------------------------------------

def _empty_rca() -> Dict[str, Any]:
    return {
        "rca_id": "",
        "generated_at": "",
        "incident_id": "",
        "device_name": "",
        "alert_type": "",
        # Step outputs
        "symptoms": [],
        "telemetry_evidence": [],
        "config_evidence": [],
        "log_evidence": [],
        "topology_evidence": [],
        "historical_matches": [],
        # Analysis outputs
        "possible_causes": [],      # list of {cause, confidence_pct, evidence}
        "most_likely_cause": "",
        "confidence_pct": 0,
        "evidence_summary": "",
        "impact": "",
        # Recommendations
        "recommended_actions": [],
        "mop_reference": "",
        "rollback_plan": "",
    }


# ---------------------------------------------------------------------------
# Cause knowledge base
# ---------------------------------------------------------------------------

CAUSE_PATTERNS: List[Dict] = [
    # VPN / IPsec
    {
        "keywords": ["vpn", "ipsec", "isakmp", "tunnel", "crypto"],
        "causes": [
            "IPsec Phase 1 ISAKMP lifetime mismatch between endpoints",
            "Pre-shared key (PSK) mismatch or key rotation without peer sync",
            "WAN link failure causing IKE keepalive timeout",
            "MTU too large for encrypted ESP overhead (fragmentation)",
        ],
        "impact": "Branch/partner connectivity severed. Mission-critical data transfers halted.",
        "base_confidence": 88,
    },
    # BGP
    {
        "keywords": ["bgp", "as-path", "peer", "neighbor", "ebgp", "ibgp"],
        "causes": [
            "BGP hold-timer expiry due to link flap or CPU overload",
            "TCP session reset on port 179 (ACL block or firewall rule)",
            "Route policy misconfiguration causing prefix withdrawal",
            "MD5 authentication key mismatch with BGP neighbor",
        ],
        "impact": "WAN routing redundancy lost. Asymmetric forwarding may cause blackholing.",
        "base_confidence": 91,
    },
    # OSPF
    {
        "keywords": ["ospf", "adjacency", "hello", "dead interval", "lsa"],
        "causes": [
            "Hello packet loss due to interface congestion or misconfigured hello/dead timers",
            "MTU mismatch between adjacent routers causing stuck EXSTART/EXCHANGE",
            "Network type mismatch (broadcast vs. point-to-point)",
            "Authentication key mismatch on OSPF-enabled interface",
        ],
        "impact": "Local subnet routing convergence lost. Traffic rerouted via suboptimal paths.",
        "base_confidence": 90,
    },
    # CPU
    {
        "keywords": ["cpu", "process", "utilization", "overload"],
        "causes": [
            "Rogue process or memory leak causing CPU saturation",
            "Routing protocol reconvergence storm triggering excessive SPF calculations",
            "Excessive SNMP polling rate causing management plane congestion",
            "Control plane policing (CoPP) misconfiguration dropping legitimate traffic",
        ],
        "impact": "Management unresponsive. Routing protocol adjacencies at risk of flap.",
        "base_confidence": 87,
    },
    # Memory
    {
        "keywords": ["memory", "ram", "oom", "heap", "swap"],
        "causes": [
            "Memory leak in routing process or diagnostic daemon",
            "Large BGP/OSPF table exceeding available TCAM/memory",
            "Software bug causing unbounded buffer growth",
            "Insufficient memory for new software image",
        ],
        "impact": "High crash risk. OOM killer may terminate critical services.",
        "base_confidence": 85,
    },
    # Packet loss / Interface
    {
        "keywords": ["packet loss", "loss", "drops", "interface", "flap", "crc"],
        "causes": [
            "Physical layer: cable degradation, SFP issue, or duplex mismatch",
            "Input/output queue overflow due to traffic burst",
            "QoS policer dropping traffic exceeding profile limits",
            "Hardware forwarding ASIC error causing selective frame drops",
        ],
        "impact": "TCP retransmissions degrade throughput. Real-time voice/video severely impacted.",
        "base_confidence": 89,
    },
    # Security / Brute force
    {
        "keywords": ["brute force", "ssh", "password spray", "attack", "intrusion", "scan"],
        "causes": [
            "External threat actor conducting credential stuffing via SSH/RDP",
            "Misconfigured service exposing management interfaces to internet",
            "Insufficient rate limiting allowing high-volume authentication attempts",
            "Compromised internal host performing lateral movement",
        ],
        "impact": "Potential unauthorized access. Management plane integrity at risk.",
        "base_confidence": 94,
    },
    # Disk / Storage
    {
        "keywords": ["disk", "partition", "storage", "log", "space"],
        "causes": [
            "Runaway log rotation filling partition (missing logrotate config)",
            "Core dump files accumulating after repeated process crashes",
            "Database tablespace growth exceeding allocated disk volume",
            "Backup retention policy not enforced, stale archives accumulating",
        ],
        "impact": "Service writes will fail when disk reaches 100%. Potential data corruption.",
        "base_confidence": 83,
    },
    # Temperature
    {
        "keywords": ["temperature", "thermal", "fan", "overheating", "cooling"],
        "causes": [
            "Fan module failure reducing airflow",
            "Datacenter CRAC unit malfunction raising ambient temperature",
            "Chassis ventilation intake blocked by cable management",
            "High ambient load from adjacent equipment",
        ],
        "impact": "Thermal protection shutdown imminent. Physical hardware damage risk.",
        "base_confidence": 92,
    },
]


# ---------------------------------------------------------------------------
# RCA Engine
# ---------------------------------------------------------------------------

class RCAEngine:
    """
    Performs structured 8-step root cause analysis and returns a complete
    RCA dict with ranked causes, confidence scores, and recommended actions.
    """

    @staticmethod
    def generate(
        alert_type: str,
        device_name: str,
        incident_id: str = "",
        telemetry: Optional[List[Dict]] = None,
        alarms: Optional[List[Dict]] = None,
        incidents: Optional[List[Dict]] = None,
        topology: Optional[Dict] = None,
        uploaded_config: Optional[str] = None,
        uploaded_logs: Optional[str] = None,
        db=None,
    ) -> Dict[str, Any]:
        """
        Run the full 8-step RCA pipeline.

        Returns a structured RCA dict.
        """
        rca = _empty_rca()
        rca["rca_id"] = f"RCA-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        rca["generated_at"] = datetime.utcnow().isoformat()
        rca["incident_id"] = incident_id
        rca["device_name"] = device_name
        rca["alert_type"] = alert_type

        text = alert_type.lower()

        # ── Step 1: Symptom Extraction ──────────────────────────────────
        rca["symptoms"] = RCAEngine._extract_symptoms(alert_type, telemetry, alarms)

        # ── Step 2: Telemetry Review ─────────────────────────────────────
        rca["telemetry_evidence"] = RCAEngine._review_telemetry(device_name, telemetry)

        # ── Step 3: Configuration Review ─────────────────────────────────
        rca["config_evidence"] = RCAEngine._review_config(uploaded_config, text)

        # ── Step 4: Log Review ───────────────────────────────────────────
        rca["log_evidence"] = RCAEngine._review_logs(uploaded_logs, text)

        # ── Step 5: Topology Review ──────────────────────────────────────
        rca["topology_evidence"] = RCAEngine._review_topology(device_name, topology)

        # ── Step 6: Historical Incident Comparison ───────────────────────
        rca["historical_matches"] = RCAEngine._compare_historical(text, incidents, db)

        # ── Step 7: Rank Possible Causes ─────────────────────────────────
        causes, impact = RCAEngine._rank_causes(text, rca)
        rca["possible_causes"] = causes
        rca["impact"] = impact

        # ── Step 8: Determine Root Cause & Confidence ────────────────────
        if causes:
            top = causes[0]
            rca["most_likely_cause"] = top["cause"]
            rca["confidence_pct"] = top["confidence_pct"]
        else:
            rca["most_likely_cause"] = f"Anomalous behavior on {device_name} related to {alert_type}"
            rca["confidence_pct"] = 60

        rca["evidence_summary"] = RCAEngine._build_evidence_summary(rca)
        rca["recommended_actions"] = RCAEngine._build_recommendations(text, causes)
        rca["rollback_plan"] = RCAEngine._build_rollback(text)

        return rca

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_symptoms(alert_type: str, telemetry: Optional[List], alarms: Optional[List]) -> List[str]:
        symptoms = [f"Primary alert: {alert_type}"]
        if telemetry:
            for t in telemetry:
                if t.get("device_name") and t.get("cpu") and t["cpu"] > 80:
                    symptoms.append(f"High CPU ({t['cpu']}%) on {t['device_name']}")
                if t.get("ram") and t["ram"] > 85:
                    symptoms.append(f"High RAM utilization ({t['ram']}%) on {t.get('device_name','?')}")
                if t.get("packet_loss") and t["packet_loss"] > 2:
                    symptoms.append(f"Packet loss detected ({t['packet_loss']}%) on {t.get('device_name','?')}")
                if t.get("interface_errors") and t["interface_errors"] > 100:
                    symptoms.append(f"Interface errors ({t['interface_errors']}) on {t.get('device_name','?')}")
        if alarms:
            for a in alarms[:3]:
                symptoms.append(f"Active alarm: {a.get('metric','?')} = {a.get('value','?')} [{a.get('severity','?')}]")
        return symptoms

    @staticmethod
    def _review_telemetry(device_name: str, telemetry: Optional[List]) -> List[str]:
        if not telemetry:
            return ["No recent telemetry available for analysis."]
        evidence = []
        for t in telemetry:
            if t.get("device_name") == device_name or not device_name:
                evidence.append(
                    f"[{t.get('timestamp','?')[:19]}] {t.get('device_name','?')}: "
                    f"CPU={t.get('cpu','?')}% RAM={t.get('ram','?')}% "
                    f"Loss={t.get('packet_loss','?')}% RTT={t.get('ping_rtt','?')}ms "
                    f"Errors={t.get('interface_errors','?')} Status={t.get('status','?')}"
                )
        if not evidence:
            # fallback: return all telemetry
            for t in telemetry[:5]:
                evidence.append(
                    f"[{t.get('timestamp','?')[:19]}] {t.get('device_name','?')}: "
                    f"CPU={t.get('cpu','?')}% RAM={t.get('ram','?')}% Status={t.get('status','?')}"
                )
        return evidence or ["No telemetry matched the target device."]

    @staticmethod
    def _review_config(config_text: Optional[str], alert_lower: str) -> List[str]:
        if not config_text:
            return ["No configuration provided for review."]
        evidence = []
        lines = config_text.split("\n")
        # Check for known risky patterns
        risky = [
            ("transport input telnet", "Telnet enabled – unencrypted management access"),
            ("snmp-server community public", "Default public SNMP community string"),
            ("no service password-encryption", "Password encryption disabled"),
            ("ip http server", "HTTP management interface enabled (use HTTPS)"),
            ("permit ip any any", "Overly permissive ACL rule detected"),
        ]
        for line in lines:
            for pattern, note in risky:
                if pattern.lower() in line.lower():
                    evidence.append(f"Config issue: {note} (line: '{line.strip()}')")
        if not evidence:
            evidence.append("Configuration reviewed – no high-risk patterns flagged in uploaded config.")
        return evidence[:8]

    @staticmethod
    def _review_logs(logs_text: Optional[str], alert_lower: str) -> List[str]:
        if not logs_text:
            return ["No log files provided for review."]
        evidence = []
        lines = logs_text.split("\n")
        error_patterns = [
            r"%\w+-\d-\w+",           # Cisco syslog mnemonics
            r"error",
            r"fail",
            r"down",
            r"reset",
            r"timeout",
            r"mismatch",
            r"denied",
            r"unreachable",
        ]
        for line in lines:
            for pat in error_patterns:
                if re.search(pat, line, re.IGNORECASE):
                    evidence.append(f"Log entry: {line.strip()[:120]}")
                    break
        return evidence[:10] or ["No error patterns found in uploaded logs."]

    @staticmethod
    def _review_topology(device_name: str, topology: Optional[Dict]) -> List[str]:
        if not topology:
            return ["No topology data available."]
        evidence = []
        nodes = topology.get("nodes", topology.get("devices", []))
        edges = topology.get("links", topology.get("edges", []))
        # Find the device in topology
        device_node = next(
            (n for n in nodes if device_name.lower() in str(n).lower()), None
        )
        if device_node:
            evidence.append(f"Device '{device_name}' found in topology graph.")
        # Find connected links
        for edge in edges:
            src = str(edge.get("source", edge.get("from", "")))
            tgt = str(edge.get("target", edge.get("to", "")))
            if device_name.lower() in src.lower() or device_name.lower() in tgt.lower():
                evidence.append(
                    f"Topology link: {src} ↔ {tgt} via {edge.get('type', edge.get('protocol','?'))}"
                )
        return evidence[:6] or [f"Device '{device_name}' not found in current topology snapshot."]

    @staticmethod
    def _compare_historical(alert_lower: str, incidents: Optional[List], db=None) -> List[str]:
        matches = []
        # Search from provided incidents list
        if incidents:
            for inc in incidents:
                desc = (inc.get("description", "") + " " + inc.get("root_cause", "")).lower()
                # Simple overlap scoring
                words = [w for w in alert_lower.split() if len(w) > 4]
                if any(w in desc for w in words):
                    matches.append(
                        f"Similar historical incident: {inc.get('id','?')} | "
                        f"{inc.get('description','?')[:80]} | "
                        f"Root Cause: {inc.get('root_cause','?')[:60]} | "
                        f"Status: {inc.get('status','?')}"
                    )
        # Search DB if available
        if db is not None and len(matches) < 3:
            try:
                from models.incident import Incident
                from sqlalchemy import or_

                words = [w for w in alert_lower.split() if len(w) > 4][:3]
                if words:
                    clauses = [Incident.description.ilike(f"%{w}%") for w in words]
                    hist = (
                        db.query(Incident)
                        .filter(Incident.status == "Resolved")
                        .filter(or_(*clauses))
                        .order_by(Incident.timestamp.desc())
                        .limit(3)
                        .all()
                    )
                    for inc in hist:
                        matches.append(
                            f"Historical (resolved): {inc.id} | {inc.description[:60]} | "
                            f"Root Cause: {inc.root_cause[:60]}"
                        )
            except Exception as e:
                logger.debug(f"Historical DB search failed: {e}")

        return matches[:5] or ["No closely matching historical incidents found."]

    @staticmethod
    def _rank_causes(alert_lower: str, rca: Dict) -> Tuple[List[Dict], str]:
        """Match alert text against cause patterns and rank by confidence."""
        impact = "Service degradation likely. Impact scope under assessment."
        candidates = []

        for pattern in CAUSE_PATTERNS:
            score = sum(1 for kw in pattern["keywords"] if kw in alert_lower)
            if score > 0:
                base = pattern["base_confidence"]
                # Boost confidence if telemetry evidence matches
                evidence_boost = min(len(rca.get("telemetry_evidence", [])) * 2, 8)
                # Boost for historical matches
                history_boost = min(
                    sum(1 for m in rca.get("historical_matches", []) if "historical" in m.lower() or "similar" in m.lower()) * 3,
                    9,
                )
                conf = min(base + evidence_boost + history_boost, 99)
                for i, cause in enumerate(pattern["causes"]):
                    # Each subsequent cause gets less confidence
                    adjusted = max(conf - i * 8, 40)
                    candidates.append({
                        "cause": cause,
                        "confidence_pct": adjusted,
                        "evidence": f"Matched keywords: {', '.join(kw for kw in pattern['keywords'] if kw in alert_lower)}",
                    })
                impact = pattern["impact"]

        # Sort by confidence descending
        candidates.sort(key=lambda x: x["confidence_pct"], reverse=True)
        # Deduplicate
        seen = set()
        unique = []
        for c in candidates:
            if c["cause"] not in seen:
                seen.add(c["cause"])
                unique.append(c)

        return unique[:5], impact

    @staticmethod
    def _build_evidence_summary(rca: Dict) -> str:
        parts = []
        if rca.get("telemetry_evidence") and rca["telemetry_evidence"] != ["No recent telemetry available for analysis."]:
            parts.append(f"{len(rca['telemetry_evidence'])} telemetry data points analysed")
        if rca.get("log_evidence") and "No log" not in rca["log_evidence"][0]:
            parts.append(f"{len(rca['log_evidence'])} log entries reviewed")
        if rca.get("config_evidence") and "No configuration" not in rca["config_evidence"][0]:
            parts.append(f"{len(rca['config_evidence'])} configuration findings")
        if rca.get("historical_matches") and "No closely" not in rca["historical_matches"][0]:
            parts.append(f"{len(rca['historical_matches'])} historical incident matches")
        if rca.get("topology_evidence") and "No topology" not in rca["topology_evidence"][0]:
            parts.append("topology graph cross-referenced")
        return "; ".join(parts) if parts else "Standard heuristic analysis applied"

    @staticmethod
    def _build_recommendations(alert_lower: str, causes: List[Dict]) -> List[str]:
        actions = []
        if not causes:
            return ["Run automated diagnostic sweep", "Engage senior engineer for manual investigation"]

        if any(w in alert_lower for w in ["vpn", "ipsec", "isakmp"]):
            actions += [
                "Verify ISAKMP lifetime matches on both endpoints (show crypto isakmp sa)",
                "Clear crypto sessions and force Phase 1 renegotiation (clear crypto isakmp sa)",
                "Capture IKE debug output to confirm mismatch type",
                "Apply Zero-Trust dual-approval config patch via Incident Control Room",
            ]
        elif any(w in alert_lower for w in ["bgp"]):
            actions += [
                "Check BGP neighbor state (show ip bgp summary)",
                "Verify TCP 179 reachability and ACL rules",
                "Review BGP hold-timer and keepalive settings",
                "Check MD5 authentication key consistency",
            ]
        elif any(w in alert_lower for w in ["ospf"]):
            actions += [
                "Verify hello/dead timers match on both ends",
                "Check interface MTU consistency (ip ospf mtu-ignore if emergency)",
                "Confirm network type settings on all adjacencies",
            ]
        elif any(w in alert_lower for w in ["cpu"]):
            actions += [
                "Identify top CPU consumers (show processes cpu sorted)",
                "Kill rogue processes if safe to do so",
                "Check routing protocol reconvergence events in syslog",
            ]
        elif any(w in alert_lower for w in ["brute force", "attack", "ssh"]):
            actions += [
                "Block attacker IP in edge firewall ACL immediately",
                "Enable SSH rate limiting and login attempt lockout",
                "Escalate to Security Analyst and SIEM team",
                "Preserve firewall logs for forensic analysis",
            ]
        else:
            actions += [
                "Run automated NOC diagnostic sweep on affected device",
                "Review syslog for correlated error messages",
                "Engage on-call Senior Engineer if severity is Critical",
            ]

        return actions

    @staticmethod
    def _build_rollback(alert_lower: str) -> str:
        if any(w in alert_lower for w in ["vpn", "ipsec", "isakmp"]):
            return "Restore previous ISAKMP lifetime: `crypto isakmp policy 10\\n lifetime 86400\\nclear crypto isakmp sa`"
        elif any(w in alert_lower for w in ["vlan"]):
            return "Remove VLAN assignment: `no vlan <id>` and restore to default access VLAN 1"
        elif any(w in alert_lower for w in ["bgp", "ospf"]):
            return "Restore original routing parameters from pre-change backup captured before deployment"
        elif any(w in alert_lower for w in ["acl", "access-list"]):
            return "Remove injected ACL rule: `no access-list <name> <rule>` – verify connectivity restored"
        return "Restore from last known-good configuration backup (show archive)"

    # ------------------------------------------------------------------
    # Format RCA as enterprise markdown report
    # ------------------------------------------------------------------

    @staticmethod
    def format_as_markdown(rca: Dict) -> str:
        lines = [
            f"# ROOT CAUSE ANALYSIS – {rca.get('rca_id', 'RCA')}",
            f"**Generated:** {rca.get('generated_at', '')[:19]}  |  "
            f"**Incident:** {rca.get('incident_id', 'N/A')}  |  "
            f"**Device:** {rca.get('device_name', 'N/A')}",
            "",
            "---",
            "",
            "## 📋 Incident Summary",
            f"**Alert Type:** {rca.get('alert_type', 'N/A')}",
            f"**Most Likely Root Cause:** {rca.get('most_likely_cause', 'N/A')}",
            f"**Confidence Score:** {rca.get('confidence_pct', 0)}%",
            f"**Evidence Basis:** {rca.get('evidence_summary', 'N/A')}",
            "",
            "## 🔍 Observed Symptoms",
        ]
        for s in rca.get("symptoms", []):
            lines.append(f"- {s}")

        lines += ["", "## 🔬 Evidence", "### Telemetry Analysis"]
        for t in rca.get("telemetry_evidence", []):
            lines.append(f"- {t}")

        if rca.get("historical_matches") and "No closely" not in rca["historical_matches"][0]:
            lines += ["", "### Historical Incident Comparison"]
            for h in rca.get("historical_matches", []):
                lines.append(f"- {h}")

        if rca.get("config_evidence") and "No configuration" not in rca["config_evidence"][0]:
            lines += ["", "### Configuration Findings"]
            for c in rca.get("config_evidence", []):
                lines.append(f"- {c}")

        if rca.get("log_evidence") and "No log" not in rca["log_evidence"][0]:
            lines += ["", "### Log Analysis"]
            for l in rca.get("log_evidence", []):
                lines.append(f"- {l}")

        lines += ["", "## 🎯 Possible Causes (Ranked by Confidence)"]
        for i, cause in enumerate(rca.get("possible_causes", [])[:5], 1):
            lines.append(
                f"{i}. **{cause['cause']}**  "
                f"*(Confidence: {cause['confidence_pct']}% | Evidence: {cause['evidence']})*"
            )

        lines += [
            "",
            "## ⚡ Impact Assessment",
            rca.get("impact", "N/A"),
            "",
            "## ✅ Recommended Actions",
        ]
        for action in rca.get("recommended_actions", []):
            lines.append(f"- {action}")

        lines += [
            "",
            "## 🔄 Rollback Plan",
            rca.get("rollback_plan", "N/A"),
            "",
            "---",
            "*This RCA was generated by the Enterprise AIOps Copilot – Phase 3 Intelligence Engine.*"
        ]

        return "\n".join(lines)
