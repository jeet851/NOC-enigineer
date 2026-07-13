"""
Risk Assessment Engine – Phase 3 Intelligence Enhancement
Pre-flight risk analysis performed before any configuration change recommendation.
Produces a structured risk report with severity, impact, affected devices,
estimated downtime, rollback complexity, confidence score, and approval requirements.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("noc.risk_engine")


# ---------------------------------------------------------------------------
# Risk levels and thresholds
# ---------------------------------------------------------------------------

class RiskLevel:
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


# Approval thresholds
APPROVAL_RULES = {
    RiskLevel.LOW: None,                            # No approval needed
    RiskLevel.MEDIUM: "Network Engineer",           # Peer review
    RiskLevel.HIGH: "Senior Engineer",              # Senior sign-off
    RiskLevel.CRITICAL: "Senior Engineer + Manager",  # Dual approval
}

# Risk scoring weights
RISK_FACTORS: List[Dict] = [
    # Factor key, matched keywords, score contribution, category
    {"keywords": ["write erase", "erase startup", "factory-reset", "format flash"],
     "score": 40, "category": "Destructive Operation", "level": RiskLevel.CRITICAL},
    {"keywords": ["reload", "reboot", "restart"],
     "score": 30, "category": "Device Restart", "level": RiskLevel.HIGH},
    {"keywords": ["no vlan", "delete vlan", "shutdown core"],
     "score": 28, "category": "VLAN Disruption", "level": RiskLevel.HIGH},
    {"keywords": ["no access-list", "no firewall", "permit ip any any"],
     "score": 25, "category": "Security Policy Removal", "level": RiskLevel.HIGH},
    {"keywords": ["router bgp", "router ospf", "network", "redistribute"],
     "score": 18, "category": "Routing Protocol Change", "level": RiskLevel.MEDIUM},
    {"keywords": ["switchport", "vlan", "trunk", "access vlan"],
     "score": 12, "category": "Layer-2 Configuration", "level": RiskLevel.MEDIUM},
    {"keywords": ["crypto isakmp", "crypto map", "tunnel", "ipsec"],
     "score": 15, "category": "VPN Configuration", "level": RiskLevel.MEDIUM},
    {"keywords": ["acl", "access-list", "deny", "permit"],
     "score": 10, "category": "ACL Modification", "level": RiskLevel.MEDIUM},
    {"keywords": ["ip address", "interface", "description"],
     "score": 8,  "category": "Interface Configuration", "level": RiskLevel.LOW},
    {"keywords": ["logging", "snmp", "ntp", "banner"],
     "score": 3,  "category": "Management Configuration", "level": RiskLevel.LOW},
]


# ---------------------------------------------------------------------------
# Risk Assessment Engine
# ---------------------------------------------------------------------------

class RiskEngine:
    """
    Analyses proposed configuration changes and returns a structured risk
    assessment before deployment approval.
    """

    @staticmethod
    def assess(
        commands_text: str,
        device_name: str = "Unknown",
        target_devices: Optional[List[str]] = None,
        incident_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform a full risk assessment on proposed commands/config.

        Parameters
        ----------
        commands_text   : The configuration commands to assess
        device_name     : Primary target device
        target_devices  : All devices affected (optional)
        incident_context: Context string from active incident

        Returns
        -------
        Structured risk assessment dict
        """
        text_lower = commands_text.lower()

        # --- Score accumulation ---
        total_score = 0
        triggered_factors = []
        highest_level = RiskLevel.LOW

        level_priority = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }

        for factor in RISK_FACTORS:
            matched_kws = [kw for kw in factor["keywords"] if kw in text_lower]
            if matched_kws:
                total_score += factor["score"]
                triggered_factors.append({
                    "category": factor["category"],
                    "matched": matched_kws,
                    "score": factor["score"],
                    "level": factor["level"],
                })
                if level_priority[factor["level"]] > level_priority[highest_level]:
                    highest_level = factor["level"]

        # --- Derive overall risk level from score ---
        if total_score >= 35:
            overall_level = RiskLevel.CRITICAL
        elif total_score >= 20:
            overall_level = RiskLevel.HIGH
        elif total_score >= 8:
            overall_level = RiskLevel.MEDIUM
        else:
            overall_level = RiskLevel.LOW

        # Take the higher of score-derived and keyword-derived level
        if level_priority.get(highest_level, 0) > level_priority.get(overall_level, 0):
            overall_level = highest_level

        # --- Estimate downtime ---
        downtime = RiskEngine._estimate_downtime(overall_level, text_lower)

        # --- Rollback complexity ---
        rollback_complexity = RiskEngine._assess_rollback_complexity(text_lower)

        # --- Affected devices ---
        devices_affected = target_devices or [device_name]
        if any(w in text_lower for w in ["all", "range", "vlan 1-"]):
            devices_affected_note = "Multiple devices potentially affected (range/all keyword detected)"
        else:
            devices_affected_note = f"{len(devices_affected)} device(s): {', '.join(devices_affected[:5])}"

        # --- Confidence score ---
        # Higher confidence when more factors were triggered
        confidence = min(70 + len(triggered_factors) * 5, 97)

        # --- Service impact ---
        service_impact = RiskEngine._assess_service_impact(overall_level, triggered_factors)

        # --- Approval requirement ---
        requires_approval = APPROVAL_RULES.get(overall_level)
        requires_approval_flag = overall_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

        return {
            "assessed_at": datetime.utcnow().isoformat(),
            "device_name": device_name,
            "devices_affected": devices_affected_note,
            "overall_risk_level": overall_level,
            "risk_score": total_score,
            "confidence_pct": confidence,
            "triggered_factors": triggered_factors,
            "service_impact": service_impact,
            "estimated_downtime": downtime,
            "rollback_complexity": rollback_complexity,
            "requires_approval": requires_approval,
            "requires_approval_flag": requires_approval_flag,
            "recommendation": RiskEngine._build_recommendation(overall_level, requires_approval),
        }

    @staticmethod
    def _estimate_downtime(level: str, text_lower: str) -> str:
        if level == RiskLevel.CRITICAL:
            return "15–60 minutes (potential full service outage)"
        elif level == RiskLevel.HIGH:
            if any(w in text_lower for w in ["reload", "reboot"]):
                return "5–15 minutes (planned reload window)"
            return "2–10 minutes (brief traffic disruption expected)"
        elif level == RiskLevel.MEDIUM:
            if any(w in text_lower for w in ["bgp", "ospf", "routing"]):
                return "30–90 seconds (routing reconvergence)"
            return "0–30 seconds (minimal impact expected)"
        else:
            return "Zero (non-disruptive configuration update)"

    @staticmethod
    def _assess_rollback_complexity(text_lower: str) -> str:
        if any(w in text_lower for w in ["write erase", "erase startup", "factory-reset", "format"]):
            return "Not Possible – destructive operation cannot be automatically reversed"
        elif any(w in text_lower for w in ["reload", "reboot"]):
            return "Complex – requires manual intervention after device comes back online"
        elif any(w in text_lower for w in ["no vlan", "delete vlan", "no access-list"]):
            return "Moderate – re-provisioning required; data may be lost"
        elif any(w in text_lower for w in ["router bgp", "router ospf", "redistribute"]):
            return "Moderate – routing reconvergence required after rollback"
        else:
            return "Simple – reverse commands available; standard rollback applicable"

    @staticmethod
    def _assess_service_impact(level: str, factors: List[Dict]) -> str:
        categories = [f["category"] for f in factors]
        if level == RiskLevel.CRITICAL:
            return "CRITICAL: Full service outage expected. All users and services impacted."
        elif level == RiskLevel.HIGH:
            if "Routing Protocol Change" in categories:
                return "HIGH: WAN routing disrupted. Traffic rerouting in progress. SLA at risk."
            elif "Device Restart" in categories:
                return "HIGH: Device unreachable during reload. All sessions terminated."
            return "HIGH: Significant service disruption. Multiple users impacted."
        elif level == RiskLevel.MEDIUM:
            if "Layer-2 Configuration" in categories:
                return "MEDIUM: Selected VLANs/interfaces affected. Localized user impact."
            if "VPN Configuration" in categories:
                return "MEDIUM: VPN tunnel renegotiation required. Brief connectivity loss."
            return "MEDIUM: Partial service impact. Specific traffic paths affected."
        else:
            return "LOW: Minimal to no service impact. Configuration update only."

    @staticmethod
    def _build_recommendation(level: str, approval: Optional[str]) -> str:
        if level == RiskLevel.CRITICAL:
            return (
                "⛔ DEPLOYMENT BLOCKED – This change carries Critical risk. "
                f"Mandatory dual approval from {approval} required before proceeding. "
                "Schedule a formal change window and notify all stakeholders."
            )
        elif level == RiskLevel.HIGH:
            return (
                f"⚠️ APPROVAL REQUIRED – High-risk change. "
                f"Obtain sign-off from {approval}. "
                "Execute during scheduled maintenance window with rollback plan ready."
            )
        elif level == RiskLevel.MEDIUM:
            return (
                f"📋 REVIEW RECOMMENDED – Medium-risk change. "
                f"Peer review by {approval} advised. "
                "Verify rollback procedure and communicate to NOC team before deploying."
            )
        else:
            return (
                "✅ SAFE TO PROCEED – Low-risk change. "
                "Standard engineering permissions sufficient. "
                "Monitor for 15 minutes post-deployment."
            )

    @staticmethod
    def format_as_markdown(risk: Dict) -> str:
        level_emoji = {
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴",
        }
        emoji = level_emoji.get(risk.get("overall_risk_level", "Low"), "⚪")

        lines = [
            f"# {emoji} RISK ASSESSMENT REPORT",
            f"**Assessed:** {risk.get('assessed_at', '')[:19]}  |  "
            f"**Device:** {risk.get('device_name', 'N/A')}",
            "",
            "---",
            "",
            f"## Overall Risk Level: `{risk.get('overall_risk_level', 'N/A')}` {emoji}",
            f"- **Risk Score:** {risk.get('risk_score', 0)} / 100",
            f"- **Confidence:** {risk.get('confidence_pct', 0)}%",
            f"- **Devices Affected:** {risk.get('devices_affected', 'N/A')}",
            "",
            "## Service Impact",
            risk.get("service_impact", "N/A"),
            "",
            "## Estimated Downtime",
            risk.get("estimated_downtime", "N/A"),
            "",
            "## Rollback Complexity",
            risk.get("rollback_complexity", "N/A"),
            "",
        ]

        if risk.get("triggered_factors"):
            lines += ["## Risk Factors Identified"]
            for f in risk["triggered_factors"]:
                lines.append(
                    f"- **{f['category']}** [{f['level']}]: "
                    f"Matched keywords: {', '.join(f['matched'])}"
                )
            lines.append("")

        if risk.get("requires_approval_flag"):
            lines += [
                "## ⚠️ Approval Required",
                f"**Approver(s):** {risk.get('requires_approval', 'N/A')}",
                "",
            ]

        lines += [
            "## Recommendation",
            risk.get("recommendation", "N/A"),
        ]

        return "\n".join(lines)
