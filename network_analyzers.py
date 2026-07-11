import re
import random
from typing import List, Dict, Any, Tuple

# ========================================================
# 1. ROUTING PROTOCOL ANALYZER
# ========================================================
class RoutingProtocolAnalyzer:
    @staticmethod
    def analyze_ospf(neighbor_output: str, interface_config: str) -> Dict[str, Any]:
        """
        Analyzes OSPF CLI output and interface configurations to identify neighbor mismatches,
        area problems, authentication, MTU mismatches, timers, and missing network statements.
        """
        root_cause = "Unknown OSPF issue."
        confidence = 50
        suggested_verify = "show ip ospf neighbor"
        suggested_fix = "N/A"
        
        # Check neighbor state
        if "INIT" in neighbor_output or "2WAY" in neighbor_output or "EXSTART" in neighbor_output:
            if "EXSTART" in neighbor_output or "EXCHANGE" in neighbor_output:
                root_cause = "OSPF MTU Mismatch. Neighbor stuck in EXSTART state because local and remote interface MTU sizes do not align."
                confidence = 95
                suggested_verify = "show ip ospf interface <interface-id> | include MTU"
                suggested_fix = "interface <interface-id>\n ip ospf mtu-ignore"
            elif "INIT" in neighbor_output:
                root_cause = "OSPF One-Way communication. Neighbor stuck in INIT state indicating that local router sees remote packets, but remote does not see local hellos (possible ACL blocking OSPF multicast 224.0.0.5)."
                confidence = 92
                suggested_verify = "show access-lists"
                suggested_fix = "access-list outside_in permit ospf any any"
            elif "2WAY" in neighbor_output and "DROTHER" in neighbor_output:
                root_cause = "OSPF normal 2-WAY neighbor state. Normal behaviour on multi-access segment for non-DR/BDR nodes."
                confidence = 90
                suggested_verify = "show ip ospf neighbor"
                suggested_fix = "! No fix required. Neighbor state is normal for segment topology."
        
        # Check authentication settings in interface config
        elif "authentication" in interface_config.lower() and "key" not in interface_config.lower():
            root_cause = "OSPF Authentication Mismatch. Authentication is enabled on the interface, but no pre-shared key is configured."
            confidence = 88
            suggested_verify = "show ip ospf interface"
            suggested_fix = "interface GigabitEthernet1\n ip ospf message-digest-key 1 md5 <key-string>"
            
        elif "area" in interface_config.lower() and "area mismatch" in neighbor_output.lower():
            root_cause = "OSPF Area Mismatch. The interface area ID does not match the area ID configured on the peer router interface."
            confidence = 95
            suggested_verify = "show ip ospf interface | include Area"
            suggested_fix = "interface GigabitEthernet1\n ip ospf 1 area <correct-area>"
            
        elif "hello" in interface_config.lower() and "dead" in interface_config.lower():
            root_cause = "OSPF Timer Mismatch. Hello interval or Dead interval timers on local router do not match peer configurations."
            confidence = 90
            suggested_verify = "show ip ospf interface | include timer"
            suggested_fix = "interface GigabitEthernet1\n no ip ospf hello-interval\n no ip ospf dead-interval"
            
        elif "router-id" in interface_config.lower() and "conflict" in neighbor_output.lower():
            root_cause = "OSPF Router ID Conflict. Local router is using the same OSPF Router ID as the remote peer."
            confidence = 98
            suggested_verify = "show ip ospf | include ID"
            suggested_fix = "router ospf 1\n router-id <new-unique-ip>"
            
        else:
            # Check for missing network statements or passive interface blocks
            if "passive-interface" in interface_config.lower():
                root_cause = "OSPF Passive Interface block. OSPF neighbor establishment is blocked because the local interface is configured as passive."
                confidence = 92
                suggested_verify = "show ip ospf interface"
                suggested_fix = "router ospf 1\n no passive-interface GigabitEthernet1"
            else:
                root_cause = "OSPF Neighbor Down. Potential physical link degradation or lack of OSPF network area statement."
                confidence = 70
                suggested_verify = "show ip ospf interface brief"
                suggested_fix = "router ospf 1\n network 10.0.0.0 0.255.255.255 area 0"

        return {
            "protocol": "OSPF",
            "root_cause": root_cause,
            "confidence_score": confidence,
            "cli_verify": suggested_verify,
            "cli_fix": suggested_fix
        }

    @staticmethod
    def analyze_bgp(summary_output: str, bgp_config: str) -> Dict[str, Any]:
        """
        Analyzes BGP CLI outputs and bgp configurations.
        """
        root_cause = "BGP Peer Down."
        confidence = 60
        suggested_verify = "show ip bgp summary"
        suggested_fix = "N/A"
        
        if "Active" in summary_output:
            root_cause = "BGP state stuck in Active. Router is actively attempting to establish TCP session (port 179) with neighbor, but peer is not responding (no route to peer, or firewall block)."
            confidence = 90
            suggested_verify = "ping <neighbor-ip>\ntelnet <neighbor-ip> 179"
            suggested_fix = "ip route <neighbor-ip> 255.255.255.255 <next-hop-ip>"
        elif "Idle" in summary_output:
            root_cause = "BGP state is Idle. Connection closed or disabled (neighbor administratively shutdown, or no remote-as statement configured)."
            confidence = 88
            suggested_verify = "show run | section bgp"
            suggested_fix = "router bgp 65001\n neighbor <neighbor-ip> no shutdown"
        elif "Connect" in summary_output:
            root_cause = "BGP stuck in Connect. TCP connection state is half-open (source IP mismatch - update-source loopback missing on multi-hop peer)."
            confidence = 94
            suggested_verify = "show ip bgp summary"
            suggested_fix = "router bgp 65001\n neighbor <neighbor-ip> update-source Loopback0"

        return {
            "protocol": "BGP",
            "root_cause": root_cause,
            "confidence_score": confidence,
            "cli_verify": suggested_verify,
            "cli_fix": suggested_fix
        }

# ========================================================
# 2. CONFIG COMPLIANCE & SECURITY ANALYZER
# ========================================================
class ConfigAnalyzer:
    @staticmethod
    def audit_config(config_text: str, vendor: str = "Cisco") -> List[Dict[str, Any]]:
        """
        Audits multi-vendor network configurations for missing routes, wrong NAT pools,
        duplicate IPs, ACL shadowing, and security vulnerabilities.
        """
        issues = []
        lines = [line.strip() for line in config_text.split("\n") if line.strip() and not line.strip().startswith("!")]
        
        # 1. Check for Duplicate IP assignments
        assigned_ips = {}
        for idx, line in enumerate(lines):
            if "ip address" in line.lower() or "address" in line.lower():
                match = re.search(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', line)
                if match:
                    ip = match.group(0)
                    if ip in assigned_ips:
                        issues.append({
                            "category": "Duplicate IP",
                            "severity": "Critical",
                            "details": f"IP address conflict detected: IP '{ip}' is assigned multiple times (lines {assigned_ips[ip]+1} and {idx+1}).",
                            "remediation": f"Verify subnet mappings and assign unique IPs on separate interfaces."
                        })
                    assigned_ips[ip] = idx
                    
        # 2. Check for shadowed ACL lines (specifically, broad permit lines preceding specific denies)
        acl_statements = []
        for idx, line in enumerate(lines):
            if "access-list" in line.lower() or "permit" in line.lower() or "deny" in line.lower():
                acl_statements.append((idx, line.lower()))
                
        has_broad_permit = False
        broad_permit_line = -1
        for idx, stmt in acl_statements:
            if "permit ip any any" in stmt or "permit any any" in stmt:
                has_broad_permit = True
                broad_permit_line = idx
            elif has_broad_permit and ("deny" in stmt or "access-list" in stmt):
                issues.append({
                    "category": "Shadowed ACL Rule",
                    "severity": "Warning",
                    "details": f"ACL shadowing threat: A broad 'permit any any' rule on line {broad_permit_line+1} precedes a more specific filter statement on line {idx+1}.",
                    "remediation": "Reorder ACL statements so that specific filters appear above catch-all permit rules."
                })
                has_broad_permit = False # reset
                
        # 3. Check for security vulnerabilities: telnet enabled, weak SNMP communities
        telnet_active = False
        snmp_public = False
        for idx, line in enumerate(lines):
            if "transport input telnet" in line.lower() or "transport input all" in line.lower():
                telnet_active = True
            elif "snmp-server community public" in line.lower() or "snmp-server community private" in line.lower():
                snmp_public = True
                
        if telnet_active:
            issues.append({
                "category": "Security compliance",
                "severity": "High",
                "details": "Telnet protocol enabled on VTY management lines (unencrypted passwords).",
                "remediation": "line vty 0 4\n transport input ssh"
            })
        if snmp_public:
            issues.append({
                "category": "Security compliance",
                "severity": "High",
                "details": "Default SNMP community string ('public' or 'private') is configured.",
                "remediation": "no snmp-server community public\nsnmp-server community <secure-string> RO"
            })
            
        # 4. Check for missing static routes to core subnets
        if not any("ip route" in l.lower() or "route" in l.lower() for l in lines) and "router" in vendor.lower():
            issues.append({
                "category": "Missing Routes",
                "severity": "Warning",
                "details": "No static default routes configured on gateway node.",
                "remediation": "ip route 0.0.0.0 0.0.0.0 <outside-gateway-ip>"
            })

        return issues

# ========================================================
# 3. SYSLOG LOG ANALYZER
# ========================================================
class LogAnalyzer:
    @staticmethod
    def parse_syslog(log_dump: str) -> List[Dict[str, Any]]:
        """
        Parses syslog block to identify failures, counts repeats, and maps correlations.
        """
        parsed_events = []
        lines = [l.strip() for l in log_dump.split("\n") if l.strip()]
        
        event_counts = {}
        for line in lines:
            # Look for common IOS syslog patterns, e.g., %LINK-3-UPDOWN or %OSPF-5-ADJCHG
            match = re.search(r'%([A-Z0-9_]+)-([0-7])-([A-Z0-9_]+):?\s*(.*)', line)
            if match:
                facility = match.group(1)
                severity = int(match.group(2))
                mnemonic = match.group(3)
                details = match.group(4)
                
                key = f"{facility}-{mnemonic}"
                if key not in event_counts:
                    event_counts[key] = {
                        "facility": facility,
                        "severity": severity,
                        "mnemonic": mnemonic,
                        "details": details,
                        "count": 0,
                        "lines": []
                    }
                event_counts[key]["count"] += 1
                event_counts[key]["lines"].append(line)
                
        # Group and build correlations
        for key, info in event_counts.items():
            correlation = "Standalone event."
            root_cause = "Diagnostic logs analysis needed."
            
            # Common correlation signatures
            if info["facility"] == "LINK" and info["mnemonic"] == "UPDOWN":
                correlation = f"Link flapped {info['count']} times. Correlates with potential layer-1 hardware cabling or SFP transceiver issue."
                root_cause = "Physical layer port flapping."
            elif info["facility"] == "OSPF" and info["mnemonic"] == "ADJCHG":
                correlation = "Correlates with link flaps or OSPF hello timeout packet losses."
                root_cause = "Routing protocol neighborhood state transition."
            elif info["facility"] == "SEC" or "deny" in info["details"].lower():
                correlation = "Correlates with firewall access control drop metrics or intrusion spraying."
                root_cause = "Security firewall packet block."
                
            parsed_events.append({
                "signature": f"%{info['facility']}-{info['severity']}-{info['mnemonic']}",
                "count": info["count"],
                "severity_label": "Critical" if info["severity"] <= 3 else ("Warning" if info["severity"] <= 5 else "Info"),
                "sample_detail": info["details"],
                "correlation_vector": correlation,
                "root_cause": root_cause
            })
            
        return parsed_events

# ========================================================
# 4. STATEFUL LAYER-BY-LAYER AI TROUBLESHOOTING ENGINE
# ========================================================
class TroubleshootingGraph:
    LAYERS = ["Physical", "Layer2", "Layer3", "Routing", "Firewall", "VPN", "Cloud", "Application"]
    
    @staticmethod
    def execute_sweep(device_name: str) -> Dict[str, Any]:
        """
        Executes a stateful layer-by-layer sweep until it encounters a failure.
        Physical -> L2 -> L3 -> Routing -> Firewall -> VPN -> Cloud -> App.
        """
        sweep_logs = []
        failure_detected = False
        failed_layer = None
        remediation_plan = None
        
        # Load active scenario mock configurations
        from fastapi_server import active_scenarios_state
        
        for layer in TroubleshootingGraph.LAYERS:
            sweep_logs.append(f"Checking layer: {layer}...")
            
            # Simulated layer evaluations
            if layer == "Physical":
                if active_scenarios_state.get("log_partition_94", False) and device_name == "db-srv-01":
                    sweep_logs.append(f"  [WARN] Physical disk space low: /var/log capacity at 94%.")
                    failed_layer = "Physical"
                    failure_detected = True
                else:
                    sweep_logs.append(f"  [PASS] Physical link status up, port speeds verified.")
                    
            elif layer == "Layer2":
                # Duplex mismatch simulation
                if device_name == "sw-core-01":
                    sweep_logs.append("  [FAIL] Duplex mismatch on interface GigabitEthernet1/0/24 (Half-Duplex vs peer Full-Duplex). High CRC errors.")
                    failed_layer = "Layer2"
                    failure_detected = True
                else:
                    sweep_logs.append("  [PASS] Spanning-Tree topology stable. No trunk mismatches.")
                    
            elif layer == "Layer3":
                sweep_logs.append("  [PASS] ARP bindings validated. No duplicate IP conflicts.")
                
            elif layer == "Routing":
                if active_scenarios_state.get("vpn_is_down", False) and device_name == "router-hq":
                    # Mismatch of timers or OSPF states could go here, but VPN is down next.
                    sweep_logs.append("  [PASS] OSPF neighbor state FULL, BGP peers converged.")
                else:
                    sweep_logs.append("  [PASS] Core routing tables synchronized.")
                    
            elif layer == "Firewall":
                if active_scenarios_state.get("ssh_spray_attack", False) and device_name == "asa-edge-01":
                    sweep_logs.append("  [FAIL] Brute-force SSH attack detected on external interface from 198.51.100.45.")
                    failed_layer = "Firewall"
                    failure_detected = True
                else:
                    sweep_logs.append("  [PASS] ACL tables checked. Traffic inspection filters compliant.")
                    
            elif layer == "VPN":
                if active_scenarios_state.get("vpn_is_down", False) and device_name == "router-hq":
                    sweep_logs.append("  [FAIL] IPsec Tunnel Phase 1 down. Lifetime parameter mismatch on crypto isakmp policy 10.")
                    failed_layer = "VPN"
                    failure_detected = True
                else:
                    sweep_logs.append("  [PASS] Cryptographic IPSec associations active (QM_IDLE).")
                    
            elif layer == "Cloud":
                sweep_logs.append("  [PASS] AWS VPC route tables and security groups aligned.")
                
            elif layer == "Application":
                if active_scenarios_state.get("server_cpu_100", False) and device_name == "app-srv-02":
                    sweep_logs.append("  [FAIL] stuck worker thread on nginx application server.")
                    failed_layer = "Application"
                    failure_detected = True
                else:
                    sweep_logs.append("  [PASS] Web app response latency matches normal SLA SLA parameters.")
                    
            if failure_detected:
                sweep_logs.append(f"Sweep halted at failed layer: {failed_layer}.")
                break
                
        # Generate remediation if failure found
        if failed_layer == "VPN":
            remediation_plan = "Configure crypto isakmp policy 10 lifetime to 28800 seconds to match remote peer gateway."
        elif failed_layer == "Layer2":
            remediation_plan = "Set interface GigabitEthernet1/0/24 duplex to FULL on local catalyst core switch."
        elif failed_layer == "Firewall":
            remediation_plan = "Apply access-list filter blocking source IP 198.51.100.45 port 22 on perimeter firewall."
        elif failed_layer == "Application":
            remediation_plan = "Kill nginx worker PID 40912 and trigger service configuration reload."
        elif failed_layer == "Physical":
            remediation_plan = "Clean old log files or increase target partition volume."
            
        return {
            "device": device_name,
            "status": "Failed" if failure_detected else "Passed",
            "logs": "\n".join(sweep_logs),
            "failed_layer": failed_layer,
            "confidence_score": 95 if failure_detected else 100,
            "remediation_plan": remediation_plan
        }
