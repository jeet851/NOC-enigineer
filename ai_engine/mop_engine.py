"""
Enhanced MOP Generator – Phase 3 Intelligence Enhancement
Produces enterprise-grade Method of Procedure documents with all required
sections: Objective, Prerequisites, Risks, Step-by-step Procedure,
Validation Steps, Rollback Procedure, and Expected Outcome.
Extends (does not replace) the existing report_generator.py.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("noc.mop_engine")


class MOPEngine:
    """
    Generates professional enterprise Method of Procedure documents suitable
    for Network Operations Center change management workflows.
    """

    @staticmethod
    def generate(
        scenario_key: str,
        command_patch: str,
        target_device: str,
        risk_assessment: Optional[Dict] = None,
        incident_id: Optional[str] = None,
        engineer_name: Optional[str] = None,
        change_window: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a structured MOP dict.

        Parameters
        ----------
        scenario_key     : Alert/scenario key (e.g., 'vpn is down')
        command_patch    : The configuration commands to deploy
        target_device    : Primary device name
        risk_assessment  : Dict from RiskEngine.assess() (optional)
        incident_id      : Associated incident ID (optional)
        engineer_name    : Approving/executing engineer (optional)
        change_window    : Planned maintenance window string (optional)
        """
        mop_id = f"MOP-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        timestamp = datetime.utcnow().isoformat()

        # Derive risk level from assessment if provided
        risk_level = "Medium"
        approval_required = "Senior Engineer"
        if risk_assessment:
            risk_level = risk_assessment.get("overall_risk_level", "Medium")
            approval_required = risk_assessment.get("requires_approval") or "Network Engineer"

        mop = {
            "mop_id": mop_id,
            "generated_at": timestamp,
            "scenario": scenario_key,
            "incident_id": incident_id or "N/A",
            "target_device": target_device,
            "engineer": engineer_name or "On-Call Network Engineer",
            "change_window": change_window or "Approved maintenance window",
            "risk_level": risk_level,
            "approval_required": approval_required,
            # MOP sections
            "objective": MOPEngine._build_objective(scenario_key, target_device),
            "prerequisites": MOPEngine._build_prerequisites(scenario_key, target_device),
            "risks": MOPEngine._build_risks(risk_assessment, scenario_key),
            "procedure_steps": MOPEngine._build_procedure(scenario_key, command_patch, target_device),
            "validation_steps": MOPEngine._build_validation(scenario_key, target_device),
            "rollback_procedure": MOPEngine._build_rollback(scenario_key, command_patch),
            "expected_outcome": MOPEngine._build_expected_outcome(scenario_key),
            "communication_plan": MOPEngine._build_communication_plan(risk_level),
        }

        return mop

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_objective(scenario: str, device: str) -> str:
        templates = {
            "vpn": f"Restore IPsec VPN tunnel connectivity on {device} by aligning ISAKMP Phase 1 lifetime parameters with the peer gateway.",
            "cpu": f"Reduce CPU utilization on {device} to normal operating levels by terminating rogue processes and reloading affected services.",
            "vlan": f"Provision the requested VLAN segment on {device} to establish Layer-2 network segregation as per the architecture design.",
            "ospf": f"Restore OSPF neighbour adjacency on {device} by correcting protocol timer or MTU mismatches.",
            "bgp": f"Re-establish BGP peer session on {device} by resolving authentication key or hold-timer configuration discrepancies.",
            "firewall": f"Mitigate active security threat by deploying ACL block rules on {device}.",
            "disk": f"Resolve disk capacity warning on {device} by executing log cleanup and adjusting log rotation policy.",
        }
        for key, text in templates.items():
            if key in scenario.lower():
                return text
        return f"Apply operational configuration change on {device} to resolve the reported issue: {scenario}."

    @staticmethod
    def _build_prerequisites(scenario: str, device: str) -> List[str]:
        common = [
            f"Operator has SSH/CLI access to {device} with Engineering privilege level",
            f"Running configuration backup captured: `show running-config` output saved",
            "Maintenance window approved and stakeholders notified",
            "Rollback plan reviewed and ready",
            "Second engineer available for dual-review (mandatory for High/Critical changes)",
        ]
        specific = []
        if any(w in scenario.lower() for w in ["vpn", "ipsec"]):
            specific += [
                "Peer gateway administrator contacted and coordinated",
                "IKE debug logging enabled on both endpoints",
                "Verify WAN link is active: `show interface GigabitEthernet0/0`",
            ]
        elif any(w in scenario.lower() for w in ["vlan"]):
            specific += [
                "Spanning Tree topology documented before change",
                "Upstream trunk ports verified as capable of carrying new VLAN",
                "IP addressing plan confirmed for new VLAN subnet",
            ]
        elif any(w in scenario.lower() for w in ["bgp", "ospf"]):
            specific += [
                "Adjacent neighbour engineers notified of planned session reset",
                "Traffic engineering paths documented for failover verification",
            ]
        return common + specific

    @staticmethod
    def _build_risks(risk_assessment: Optional[Dict], scenario: str) -> List[Dict]:
        risks = []
        if risk_assessment:
            risks.append({
                "risk": f"Overall deployment risk: {risk_assessment.get('overall_risk_level', 'Medium')}",
                "likelihood": "Possible",
                "impact": risk_assessment.get("service_impact", "Service disruption possible"),
                "mitigation": "Execute during approved maintenance window with rollback plan active",
            })
            for factor in risk_assessment.get("triggered_factors", [])[:3]:
                risks.append({
                    "risk": f"{factor['category']} modification",
                    "likelihood": "Likely during execution",
                    "impact": f"Level: {factor['level']}",
                    "mitigation": "Follow step-by-step procedure strictly. Abort if unexpected output occurs.",
                })
        else:
            # Default risks
            risks = [
                {
                    "risk": "Transient traffic interruption during configuration push",
                    "likelihood": "Possible",
                    "impact": "Brief packet loss (< 30 seconds for most changes)",
                    "mitigation": "Deploy during low-traffic window. Monitor in real-time.",
                },
                {
                    "risk": "Configuration syntax error causing device instability",
                    "likelihood": "Low (mitigated by pre-validation)",
                    "impact": "Device unreachable if critical commands are malformed",
                    "mitigation": "Pre-validate all commands with syntax checker before deployment.",
                },
                {
                    "risk": "Rollback failure if startup config is not backed up",
                    "likelihood": "Low",
                    "impact": "Extended outage if rollback is not possible",
                    "mitigation": "Always capture `show running-config` backup before any change.",
                },
            ]
        return risks

    @staticmethod
    def _build_procedure(scenario: str, command_patch: str, device: str) -> List[Dict]:
        steps = [
            {
                "step": 1,
                "action": "Establish secure CLI session",
                "command": f"ssh admin@{device}",
                "expected": "Authentication successful. Privileged EXEC prompt displayed.",
                "abort_if": "Authentication fails or SSH connection refused.",
            },
            {
                "step": 2,
                "action": "Capture pre-change configuration backup",
                "command": "show running-config",
                "expected": "Full configuration displayed. Save to change record.",
                "abort_if": "Device unresponsive or partial config returned.",
            },
            {
                "step": 3,
                "action": "Verify current state before change",
                "command": MOPEngine._get_verification_command(scenario),
                "expected": "Baseline state documented for post-change comparison.",
                "abort_if": "Unexpected state that contradicts the incident description.",
            },
            {
                "step": 4,
                "action": "Enter configuration mode",
                "command": "configure terminal",
                "expected": "Config prompt: (config)#",
                "abort_if": "Access denied – verify privilege level.",
            },
            {
                "step": 5,
                "action": "Apply configuration patch",
                "command": command_patch,
                "expected": "Commands accepted without error messages.",
                "abort_if": "Any % error message. Exit immediately and review.",
            },
            {
                "step": 6,
                "action": "Exit configuration mode",
                "command": "end",
                "expected": "Return to privileged EXEC mode.",
                "abort_if": "N/A",
            },
            {
                "step": 7,
                "action": "Save configuration",
                "command": "write memory",
                "expected": "Building configuration... [OK]",
                "abort_if": "Write failure – check flash storage availability.",
            },
        ]
        # Add scenario-specific final steps
        if any(w in scenario.lower() for w in ["vpn", "ipsec"]):
            steps.append({
                "step": 8,
                "action": "Clear stale crypto sessions to force renegotiation",
                "command": "clear crypto isakmp sa",
                "expected": "IKE Phase 1 renegotiation initiated. State transitions to QM_IDLE.",
                "abort_if": "State remains MM_NO_STATE after 60 seconds.",
            })
        elif any(w in scenario.lower() for w in ["cpu", "nginx", "process"]):
            steps.append({
                "step": 8,
                "action": "Verify service restoration",
                "command": "show processes cpu sorted | head",
                "expected": "CPU drops below 50%. Rogue process absent from top list.",
                "abort_if": "CPU remains above 90%.",
            })
        return steps

    @staticmethod
    def _get_verification_command(scenario: str) -> str:
        if any(w in scenario.lower() for w in ["vpn", "ipsec"]):
            return "show crypto isakmp sa"
        elif any(w in scenario.lower() for w in ["bgp"]):
            return "show ip bgp summary"
        elif any(w in scenario.lower() for w in ["ospf"]):
            return "show ip ospf neighbor"
        elif any(w in scenario.lower() for w in ["vlan"]):
            return "show vlan brief"
        elif any(w in scenario.lower() for w in ["cpu"]):
            return "show processes cpu sorted | head"
        else:
            return "show ip interface brief"

    @staticmethod
    def _build_validation(scenario: str, device: str) -> List[str]:
        common = [
            f"Verify running-config matches expected post-change state",
            "Confirm no error messages in `show log | last 20`",
            "Test end-to-end connectivity via ICMP ping from affected endpoints",
        ]
        specific = []
        if any(w in scenario.lower() for w in ["vpn", "ipsec"]):
            specific = [
                "Run `show crypto isakmp sa` – expected state: QM_IDLE (fully connected)",
                "Verify Phase 2 security associations: `show crypto ipsec sa`",
                "Ping across tunnel from both ends to confirm bi-directional traffic",
                "Monitor syslog for %ASA-5-713008 (ISAKMP SA established)",
            ]
        elif any(w in scenario.lower() for w in ["bgp"]):
            specific = [
                "Run `show ip bgp summary` – neighbour state: Established",
                "Verify received prefix count matches baseline",
                "Confirm routing table has expected remote prefixes",
            ]
        elif any(w in scenario.lower() for w in ["vlan"]):
            specific = [
                "Run `show vlan id <id>` – VLAN active and ports assigned",
                "Run `show interface status` – interfaces in correct VLAN",
                "Test inter-VLAN routing if L3 switch is involved",
            ]
        elif any(w in scenario.lower() for w in ["cpu"]):
            specific = [
                "Run `show processes cpu sorted` – CPU below 50%",
                "Run `uptime` or check load average via SNMP poll",
                "Verify HTTP/HTTPS response times are normal",
            ]
        return common + specific

    @staticmethod
    def _build_rollback(scenario: str, command_patch: str) -> str:
        if any(w in scenario.lower() for w in ["vpn", "ipsec"]):
            return (
                "1. Re-enter the previous ISAKMP lifetime value:\n"
                "```\nconfigure terminal\ncrypto isakmp policy 10\n lifetime 86400\nend\n"
                "clear crypto isakmp sa\nwrite memory\n```\n"
                "2. Verify peer re-establishes with original parameters."
            )
        elif any(w in scenario.lower() for w in ["vlan"]):
            return (
                "1. Remove VLAN and restore default access:\n"
                "```\nconfigure terminal\ninterface range GigabitEthernet1/0/1 - 12\n"
                " no switchport access vlan\n switchport access vlan 1\nno vlan <id>\nend\n"
                "write memory\n```\n"
                "2. Verify STP reconverges."
            )
        elif any(w in scenario.lower() for w in ["bgp", "ospf"]):
            return (
                "1. Restore original routing parameters from backup.\n"
                "2. Clear neighbor sessions to force reconvergence.\n"
                "3. Verify prefix counts match pre-change baseline."
            )
        else:
            # Generic rollback from first command line
            first_cmd = command_patch.strip().split("\n")[0] if command_patch else "configuration"
            return (
                f"1. Remove the applied configuration: `no {first_cmd}`\n"
                "2. Restore from backup config captured in Step 2.\n"
                "3. Run `write memory` to save rollback state.\n"
                "4. Verify service restoration within 5 minutes."
            )

    @staticmethod
    def _build_expected_outcome(scenario: str) -> str:
        if any(w in scenario.lower() for w in ["vpn", "ipsec"]):
            return (
                "IPsec VPN tunnel transitions to QM_IDLE (fully established) state. "
                "End-to-end connectivity between all remote sites restored. "
                "SLA compliance metrics return to green."
            )
        elif any(w in scenario.lower() for w in ["vlan"]):
            return (
                "New VLAN segment active across all target switches. "
                "Assigned ports visible in `show vlan` output. "
                "Traffic segregation enforced per network security design."
            )
        elif any(w in scenario.lower() for w in ["cpu"]):
            return (
                "CPU utilization drops below normal operating threshold (< 50%). "
                "Management interfaces responsive. "
                "No further process CPU alerts triggered."
            )
        elif any(w in scenario.lower() for w in ["bgp"]):
            return (
                "BGP peer session re-established (Established state). "
                "Prefix counts match pre-incident baseline. "
                "WAN routing redundancy fully restored."
            )
        elif any(w in scenario.lower() for w in ["firewall", "acl", "attack"]):
            return (
                "Malicious traffic blocked at perimeter. "
                "ACL hit counters incrementing on block rule. "
                "SSH authentication failure rate drops to zero."
            )
        else:
            return (
                "Configuration change applied successfully. "
                "Service parameters return to normal operating baseline. "
                "No further alerts triggered within 15-minute monitoring window."
            )

    @staticmethod
    def _build_communication_plan(risk_level: str) -> str:
        if risk_level in ("High", "Critical"):
            return (
                "1. Notify NOC Team Lead 30 minutes before change window.\n"
                "2. Post in #network-ops Slack channel: Change start/end times.\n"
                "3. Email distribution list: operations@company.com\n"
                "4. Update ServiceNow change ticket to 'In Progress'.\n"
                "5. Bridge call open for duration of change."
            )
        elif risk_level == "Medium":
            return (
                "1. Notify NOC on-call engineer before starting.\n"
                "2. Post in #network-ops Slack channel.\n"
                "3. Update change ticket status."
            )
        else:
            return "Notify NOC via Slack channel #network-ops after completion."

    # ------------------------------------------------------------------
    # Format as enterprise markdown document
    # ------------------------------------------------------------------

    @staticmethod
    def format_as_markdown(mop: Dict) -> str:
        risk_emoji = {"Low": "🟢", "Medium": "🟡", "High": "🟠", "Critical": "🔴"}.get(
            mop.get("risk_level", "Medium"), "⚪"
        )
        lines = [
            f"# METHOD OF PROCEDURE – {mop.get('mop_id', 'MOP')}",
            f"**Generated:** {mop.get('generated_at','')[:19]}  |  "
            f"**Incident:** {mop.get('incident_id','N/A')}  |  "
            f"**Device:** {mop.get('target_device','N/A')}",
            f"**Engineer:** {mop.get('engineer','N/A')}  |  "
            f"**Change Window:** {mop.get('change_window','N/A')}",
            f"**Risk Level:** {risk_emoji} {mop.get('risk_level','N/A')}  |  "
            f"**Approval:** {mop.get('approval_required','N/A')}",
            "",
            "---",
            "",
            "## 🎯 Objective",
            mop.get("objective", "N/A"),
            "",
            "## ✅ Prerequisites",
        ]
        for prereq in mop.get("prerequisites", []):
            lines.append(f"- {prereq}")

        lines += ["", "## ⚠️ Risk Summary"]
        for risk in mop.get("risks", []):
            lines.append(
                f"- **{risk['risk']}**: Likelihood: {risk['likelihood']} | "
                f"Impact: {risk['impact']} | Mitigation: {risk['mitigation']}"
            )

        lines += ["", "## 📋 Step-by-Step Procedure"]
        for step in mop.get("procedure_steps", []):
            lines += [
                f"### Step {step['step']}: {step['action']}",
                f"```\n{step['command']}\n```",
                f"**Expected:** {step['expected']}",
                f"**Abort If:** {step['abort_if']}",
                "",
            ]

        lines += ["## 🔍 Validation Steps"]
        for v in mop.get("validation_steps", []):
            lines.append(f"- {v}")

        lines += [
            "",
            "## 🔄 Rollback Procedure",
            mop.get("rollback_procedure", "N/A"),
            "",
            "## 🏁 Expected Outcome",
            mop.get("expected_outcome", "N/A"),
            "",
            "## 📣 Communication Plan",
            mop.get("communication_plan", "N/A"),
            "",
            "---",
            "*This MOP was generated by the Enterprise AIOps Copilot – Phase 3 Intelligence Engine.*"
        ]

        return "\n".join(lines)
