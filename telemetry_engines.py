import random
import re
from typing import List, Dict, Any, Tuple

# ========================================================
# 1. PING MONITOR & FAILURE DIAGNOSTIC
# ========================================================
class PingMonitor:
    @staticmethod
    def ping_device(ip_address: str, simulated_failure_type: str = None) -> Dict[str, Any]:
        """
        Simulates running ICMP ping tests to gather latency statistics,
        packet loss, jitter, and diagnose failure causes.
        """
        if simulated_failure_type:
            # Determine the root cause of the failure
            diagnosis = "Device down"
            if simulated_failure_type == "routing":
                diagnosis = "Routing issue: Destination network unreachable in local VRF."
            elif simulated_failure_type == "firewall":
                diagnosis = "Firewall issue: Drop by firewall security policy policy-map."
            elif simulated_failure_type == "acl":
                diagnosis = "ACL issue: Blocked by implicit deny in inbound Access Control List."
            elif simulated_failure_type == "isp":
                diagnosis = "ISP issue: High packet drop on upstream provider peering hop."
            elif simulated_failure_type == "vpn":
                diagnosis = "VPN issue: Phase 1 ISAKMP SA not established due to configuration mismatch."
            elif simulated_failure_type == "mpls":
                diagnosis = "MPLS issue: Label Distribution Protocol (LDP) session down between PE routers."
            elif simulated_failure_type == "interface":
                diagnosis = "Interface down: Target port state is administratively shutdown."
                
            return {
                "ip": ip_address,
                "status": "Failed",
                "avg_latency": 0.0,
                "max_latency": 0.0,
                "min_latency": 0.0,
                "packet_loss": 100.0,
                "jitter": 0.0,
                "diagnosis": diagnosis,
                "rtt_trend": [0.0] * 10
            }
            
        # Normal healthy execution
        avg_lat = round(random.uniform(2.0, 15.0), 2)
        min_lat = round(avg_lat - random.uniform(0.5, 1.5), 2)
        max_lat = round(avg_lat + random.uniform(1.0, 4.0), 2)
        jitter = round(random.uniform(0.1, 1.2), 2)
        loss = 0.0
        
        # Simulate occasional minor loss (e.g. 1%)
        if random.random() < 0.02:
            loss = 1.0
            
        trend = [round(avg_lat + random.uniform(-1.5, 1.5), 2) for _ in range(10)]
        
        return {
            "ip": ip_address,
            "status": "Healthy",
            "avg_latency": avg_lat,
            "max_latency": max_lat,
            "min_latency": max_lat,
            "packet_loss": loss,
            "jitter": jitter,
            "diagnosis": "Reachability verified. No issues detected.",
            "rtt_trend": trend
        }

# ========================================================
# 2. PATH ANALYZER (TRACEROUTE COMPARATOR)
# ========================================================
class PathAnalyzer:
    @staticmethod
    def run_traceroute(source: str, destination: str, expected_path: List[str], current_path: List[str]) -> Dict[str, Any]:
        """
        Compares expected path against current path, highlights changed hops,
        and detects ISP/MPLS/VPN failovers.
        """
        path_changed = expected_path != current_path
        changed_hop_index = -1
        change_type = None
        
        if path_changed:
            # Find first mismatching hop
            for idx, (exp, cur) in enumerate(zip(expected_path, current_path)):
                if exp != cur:
                    changed_hop_index = idx
                    break
            if changed_hop_index == -1 and len(current_path) != len(expected_path):
                changed_hop_index = min(len(expected_path), len(current_path))
                
            # Classify change
            if any("mpls" in hop.lower() or "pe-" in hop.lower() for hop in current_path):
                change_type = "MPLS Failover"
            elif any("vpn" in hop.lower() or "tunnel" in hop.lower() for hop in current_path):
                change_type = "Backup VPN Activation"
            elif any("backup" in hop.lower() or "isp-2" in hop.lower() for hop in current_path):
                change_type = "ISP Failover"
            else:
                change_type = "Path Change Detected"
                
        return {
            "source": source,
            "destination": destination,
            "expected_path": expected_path,
            "current_path": current_path,
            "path_changed": path_changed,
            "changed_hop_index": changed_hop_index,
            "change_type": change_type,
            "visual_diff": PathAnalyzer._format_visual_diff(expected_path, current_path, changed_hop_index)
        }
        
    @staticmethod
    def _format_visual_diff(expected: List[str], current: List[str], mismatch_idx: int) -> str:
        diff_lines = []
        max_len = max(len(expected), len(current))
        for i in range(max_len):
            exp_hop = expected[i] if i < len(expected) else "---"
            cur_hop = current[i] if i < len(current) else "---"
            
            if i == mismatch_idx:
                diff_lines.append(f"Hop {i+1}: expected [{exp_hop}]  ===>  CURRENT: [{cur_hop}]  << (CHANGED HOP) >>")
            elif i > mismatch_idx and mismatch_idx != -1:
                diff_lines.append(f"Hop {i+1}: expected [{exp_hop}]  ===>  CURRENT: [{cur_hop}]  (Alt Path)")
            else:
                diff_lines.append(f"Hop {i+1}: [{exp_hop}] (Unchanged)")
        return "\n".join(diff_lines)

# ========================================================
# 3. ASYMMETRIC ROUTING DETECTOR
# ========================================================
class AsymmetricRoutingDetector:
    @staticmethod
    def check_routing_symmetry(forward_path: List[str], return_path: List[str]) -> Dict[str, Any]:
        """
        Compares forward path vs return path (reversed) to locate asymmetry.
        """
        # A symmetrical return path is the forward path in reverse
        expected_reversed = list(reversed(forward_path))
        
        # Clean paths for comparison (ignoring hop names, comparing IPs or basic node IDs)
        def clean_hop(hop: str) -> str:
            match = re.search(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', hop)
            return match.group(0) if match else hop.split(" ")[0].lower()
            
        clean_expected = [clean_hop(h) for h in expected_reversed]
        clean_return = [clean_hop(h) for h in return_path]
        
        asymmetric = clean_expected != clean_return
        
        causes = []
        if asymmetric:
            causes = [
                "OSPF Cost mismatch: Metric values differ on parallel redundant segments.",
                "ECMP (Equal-Cost Multi-Path) hashing: Inbound and outbound links hashed to separate paths.",
                "BGP Local Preference: AS egress utilizes primary link, while return provider routing favors backup exchange.",
                "Policy Based Routing (PBR): Explicit next-hop router overrides global route table on return segment.",
                "Static Route mapping: Missing static routes on peer interface leading to default route return.",
                "SD-WAN Policy routing: SLA profiles route voice traffic over MPLS forward and business-internet return."
            ]
            
        return {
            "asymmetric_detected": asymmetric,
            "forward_path": forward_path,
            "return_path": return_path,
            "possible_causes": causes,
            "visual_diagram": AsymmetricRoutingDetector._generate_symmetry_visual(forward_path, return_path)
        }
        
    @staticmethod
    def _generate_symmetry_visual(forward: List[str], return_p: List[str]) -> str:
        visual = "================ ASYMMETRIC ROUTING TOPOLOGY ================\n"
        visual += "FORWARD PATH: " + " -> ".join([f"[{f.split(' ')[0]}]" for f in forward]) + "\n"
        visual += "RETURN PATH:  " + " <- ".join([f"[{r.split(' ')[0]}]" for r in return_p]) + "\n"
        visual += "============================================================="
        return visual

# ========================================================
# 4. CONGESTION ANALYZER
# ========================================================
class CongestionAnalyzer:
    @staticmethod
    def diagnose_congestion(device_name: str, cpu: int, ram: int, port_utilization: float, drop_rate: float, storm_detected: bool = False) -> Dict[str, Any]:
        """
        Diagnoses specific types of network and host congestions.
        """
        congestion_type = "None"
        cause = "Operating parameters within healthy limits."
        severity = "Info"
        confidence = 100
        recommendation = "Maintain current monitoring thresholds."
        expected_impact = "No performance impact."
        
        if storm_detected:
            congestion_type = "Broadcast Storm"
            cause = "Layer-2 Spanning Tree Loop or faulty network interface card flooding broadcast frames."
            severity = "Critical"
            confidence = 94
            recommendation = "Verify STP bridge root configuration; enable broadcast storm-control limit on core trunks."
            expected_impact = "Complete link starvation, switches running high CPU load, overall network dropouts."
            
        elif cpu >= 90:
            congestion_type = "Router CPU Congestion"
            cause = "OSPF router SPF database recalculation surge due to flapping core link or stuck regex process thread."
            severity = "Critical"
            confidence = 92
            recommendation = "Isolate flapping interfaces; adjust OSPF LSA throttle timers; restart stuck services."
            expected_impact = "Control-plane degradation, routing neighbor state loss (Dead timer expirations)."
            
        elif port_utilization >= 85 and drop_rate >= 2.0:
            congestion_type = "WAN Congestion"
            cause = "High bandwidth replication transfer or database sync saturating edge WAN trunk link."
            severity = "Warning"
            confidence = 88
            recommendation = "Apply Class-Based Weighted Fair Queueing (CBWFQ) QoS policies; throttle replication bandwidth during business hours."
            expected_impact = "Jitter spikes and packet drops on latency-sensitive voice/video protocols."
            
        elif drop_rate >= 5.0:
            congestion_type = "Switch Buffer Congestion"
            cause = "Microburst traffic spikes exceeding physical egress port memory buffer queues."
            severity = "Warning"
            confidence = 85
            recommendation = "Enable egress port-channel flow-control; verify Spanning-Tree interface priorities."
            expected_impact = "TCP global synchronization and retransmission delays."
            
        return {
            "device": device_name,
            "congestion_detected": congestion_type != "None",
            "congestion_type": congestion_type,
            "cause": cause,
            "severity": severity,
            "confidence_score": confidence,
            "recommendation": recommendation,
            "expected_impact": expected_impact
        }

# ========================================================
# 5. INTERFACE ANALYZER
# ========================================================
class InterfaceAnalyzer:
    @staticmethod
    def monitor_interfaces(device_name: str, site: str) -> List[Dict[str, Any]]:
        """
        Generates simulated physical and logical interface statistics for analysis.
        """
        interfaces = []
        
        # Simulate base port mappings
        if "router" in device_name or "gw" in device_name:
            ports = ["GigabitEthernet1", "GigabitEthernet2", "Tunnel10"]
        elif "switch" in device_name or "core" in device_name:
            ports = ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2", "GigabitEthernet1/0/24", "Vlan10", "Vlan20"]
        else:
            ports = ["eth0"]
            
        for port in ports:
            is_up = True
            speed = 1000
            duplex = "Full"
            crc_errors = 0
            in_errors = 0
            out_errors = 0
            drops = 0
            discard = 0
            utilization = round(random.uniform(5.0, 45.0), 2)
            temp = round(random.uniform(34.0, 48.0), 1)
            sfp_health = "Healthy"
            mismatch_duplex = False
            mismatch_speed = False
            flapping = False
            
            # Anomaly injection for testing
            if device_name == "sw-core-01" and port == "GigabitEthernet1/0/24":
                # Duplex mismatch case
                duplex = "Half"
                crc_errors = random.randint(120, 850)
                in_errors = random.randint(45, 230)
                mismatch_duplex = True
                utilization = 15.2
                sfp_health = "Degraded (High CRC rates)"
                
            elif device_name == "mumbai-gw" and port == "GigabitEthernet2":
                # Link flapping simulation
                flapping = True
                drops = random.randint(22, 110)
                utilization = round(random.uniform(0.0, 95.0), 1)
                
            interfaces.append({
                "interface": port,
                "status": "Up" if is_up else "Down",
                "speed_mbps": speed,
                "duplex": duplex,
                "crc_errors": crc_errors,
                "input_errors": in_errors,
                "output_errors": out_errors,
                "drops": drops,
                "discard": discard,
                "utilization_pct": utilization,
                "temperature_c": temp,
                "sfp_health": sfp_health,
                "duplex_mismatch": mismatch_duplex,
                "speed_mismatch": mismatch_speed,
                "flapping": flapping
            })
            
        return interfaces

# ========================================================
# 6. NETWORK HEALTH ENGINE (HEALTH SCORES CALCULATOR)
# ========================================================
class NetworkHealthEngine:
    @staticmethod
    def get_layer_scores(devices: List[Dict[str, Any]], active_alarms: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Synthesizes raw alerts and telemetry into categorical Layer 1-7 scores.
        """
        # Baseline scores
        physical_score = 100
        layer2_score = 100
        layer3_score = 100
        routing_score = 100
        firewall_score = 100
        vpn_score = 100
        cloud_score = 100
        
        # Deduct based on device statuses
        for dev in devices:
            status = dev.get("status", "Healthy").lower()
            if status == "warning":
                physical_score -= 5
                layer3_score -= 3
            elif status == "critical":
                physical_score -= 15
                layer3_score -= 10
                
        # Deduct based on active alarms
        for alarm in active_alarms:
            severity = alarm.get("severity", "Warning").lower()
            metric = alarm.get("metric", "").lower()
            
            deduction = 10 if severity == "warning" else 25
            
            if "disk" in metric or "cpu" in metric or "hardware" in metric:
                physical_score -= deduction
            elif "loop" in metric or "stp" in metric or "vlan" in metric:
                layer2_score -= deduction
            elif "ip" in metric or "subnet" in metric or "dns" in metric:
                layer3_score -= deduction
            elif "ospf" in metric or "bgp" in metric or "routing" in metric:
                routing_score -= deduction
            elif "spray" in metric or "brute" in metric or "firewall" in metric or "acl" in metric:
                firewall_score -= deduction
            elif "vpn" in metric or "isakmp" in metric or "ipsec" in metric:
                vpn_score -= deduction
            elif "aws" in metric or "azure" in metric or "vpc" in metric:
                cloud_score -= deduction
                
        # Normalize boundaries [10, 100]
        def clamp(score: int) -> int:
            return max(10, min(100, score))
            
        scores = {
            "physical": clamp(physical_score),
            "layer2": clamp(layer2_score),
            "layer3": clamp(layer3_score),
            "routing": clamp(routing_score),
            "firewall": clamp(firewall_score),
            "vpn": clamp(vpn_score),
            "cloud": clamp(cloud_score)
        }
        
        # Compute Overall health score as weighted average
        weights = {
            "physical": 0.15,
            "layer2": 0.15,
            "layer3": 0.15,
            "routing": 0.20,
            "firewall": 0.15,
            "vpn": 0.10,
            "cloud": 0.10
        }
        
        overall = sum(scores[layer] * weights[layer] for layer in scores)
        scores["overall"] = clamp(int(overall))
        
        return scores
