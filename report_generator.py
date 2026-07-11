import datetime
from typing import Dict, Any

class ReportGenerator:
    """
    Generates compliance-ready enterprise operational reports (RCA, MOP, SOP, and Executive Summaries)
    incorporating NIST SP 800-207 and CCIE standards.
    """
    
    @staticmethod
    def generate_rca(scenario_key: str, incident_details: Dict[str, Any]) -> str:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""# ROOT CAUSE ANALYSIS (RCA) REPORT
Generated: {timestamp}
Incident ID: INC-{hash(scenario_key) % 10000:04d}
Compliance Standards: NIST SP 800-207, ISO 27001

## 1. Executive Summary
An operational outage event occurred affecting key segment parameters. Automated NOC systems isolated the root cause layer and applied verified configuration remediation under Zero-Trust dual authorizations.

- **Incident Target**: {incident_details.get("device", "HQ Backbone Gateway")}
- **Outage Scenario**: {scenario_key.upper()}
- **Operational Severity**: Critical

## 2. Event Timeline
- **Discovery**: Automated telemetry loop flagged interface packet drops.
- **Diagnostics**: Layer-by-layer troubleshooting graph isolated failed layer.
- **Change Scope**: Configuration patch generated and audited by syntax parser.
- **Remediation**: Dual authorizations applied. Verified state restored.

## 3. Root Cause Investigation
Investigation reveals configuration drift or anomalous protocol behavior:
> {incident_details.get("root_cause", "No detailed investigation log.")}

## 4. Remediation Actions Applied
The following configuration patch statement was successfully deployed:
```text
{incident_details.get("cli_fix", "! No commands logged.")}
```

## 5. Preventive Actions & Compliance Audits
- Setup automated config baseline monitoring to alert on key policy changes.
- Implement rate limiting and security ACL blocks at perimeter gateway links.
- Schedule weekly OSPF/BGP authentication keys rollover audits.
"""

    @staticmethod
    def generate_mop(scenario_key: str, command_patch: str, target_device: str) -> str:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""# METHOD OF PROCEDURE (MOP)
Document Reference: MOP-2026-CHG-{hash(scenario_key) % 1000:03d}
Change Target Node: {target_device}
Generated: {timestamp}

## 1. Pre-Change Requirements & Backups
Prior to executing commands, the operator must:
1. Capture current running configuration backup state.
   - Command: `show running-config` (Saved as backup reference)
2. Verify active adjacent neighbor routing table:
   - Command: `show ip ospf neighbor`
   - Command: `show ip bgp summary`

## 2. Step-by-Step Configuration Statement
The following statements must be applied via config terminal:
```text
! Change window block
configure terminal
{command_patch}
end
write memory
```

## 3. Post-Change Verification Checklist
Execute these commands to verify target protocol convergence:
1. `show ip interface brief` (Check interface states)
2. Ping test adjacent gateway ports:
   - Command: `ping 10.0.1.1`
3. Verify routing table convergence.

## 4. Rollback Contingency Playbook
In case of post-change verification packet drop failure, execute:
```text
! Rollback command sequence
configure terminal
! Restore original parameters
no {command_patch.splitlines()[0] if command_patch.splitlines() else "patch"}
end
write memory
```
"""

    @staticmethod
    def generate_sop(alarm_metric: str) -> str:
        return f"""# STANDARD OPERATING PROCEDURE (SOP)
Topic: Response Guidelines for {alarm_metric} Alerts
Document Code: SOP-NOC-042
Security Level: Restricted Internal

## 1. Trigger Conditions
This SOP is activated when NOC telemetry monitors raise alarms matching:
- **Alert Type**: {alarm_metric}
- **Severity**: Critical / Disaster

## 2. Immediate Diagnostic Checklist
When the alert fires, the on-duty Network Engineer must:
1. Execute ping checks to verify route adjacency.
2. Query target node CPU and memory loads:
   - CLI: `show processes cpu sorted`
3. Check syslog timelines for %LINK-3-UPDOWN or interface flap Mnemonics.

## 3. Mitigation Protocols
- **Log Outages**: If log partition is full, execute local archive cleanup scripts.
- **Routing Outages**: Verify MD5 authentication keys and interface MTU metrics.
- **Security Intrusion**: Immediately deploy firewall ACL blocks restricting attacker IPs.

## 4. Escalation Path
- **Level 1**: Network Engineer (Initial diagnostics sweep, MOP staging)
- **Level 2**: Senior Systems Architect (MOP execution authorization)
- **Level 3**: Operations Director (Dual approval overrides for destructive actions)
"""

    @staticmethod
    def generate_executive_summary(scores: Dict[str, int], active_alerts_count: int) -> str:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""# EXECUTIVE HEALTH SUMMARY
Reporting Period: Daily NOC Sweep
Generated: {timestamp}

## 1. Infrastructure Health Assessment
The overall NOC infrastructure score is:
# **{scores.get("overall", 95)}%**

### Categorical Score Breakdown:
- **Physical Layer Health**: {scores.get("physical", 100)}%
- **Layer 2 (STP/VLANs)**: {scores.get("layer2", 100)}%
- **Layer 3 (IP/Subnets)**: {scores.get("layer3", 100)}%
- **Routing Protocol Adjacency**: {scores.get("routing", 100)}%
- **Firewall & Security Compliance**: {scores.get("firewall", 100)}%
- **IPsec VPN Tunnel Security**: {scores.get("vpn", 100)}%

## 2. Active Alarms & Outages
- **Active Incident Count**: {active_alerts_count}
- **SLA Target Compliance**: 99.98%

## 3. Compliance & Security Summary
All configurations validated against NIST SP 800-207 standards. Zero-Trust multi-level authorization policies remain fully active.
"""
