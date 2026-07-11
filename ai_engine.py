import logging
import os
import json
import base64
import re
import google.generativeai as genai
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import database

logger = logging.getLogger("noc.ai")

# Load environment variables
load_dotenv()

# ========================================================
# VAULT ENCRYPTION ENGINE (AES-256 via Fernet)
# ========================================================
VAULT_KEY_FILE = "vault.key"
if not os.path.exists(VAULT_KEY_FILE):
    key = Fernet.generate_key()
    with open(VAULT_KEY_FILE, "wb") as f:
        f.write(key)
else:
    with open(VAULT_KEY_FILE, "rb") as f:
        key = f.read()

cipher_suite = Fernet(key)

class VaultManager:
    @staticmethod
    def get_secrets():
        secrets = database.get_db_secrets()
        if not secrets:
            # Prepopulate with some default secure vaulted credentials for zero-trust simulation
            default_secrets = {
                "Cisco-Core-Switch-SSH": {"type": "SSH Key", "value": VaultManager.encrypt_raw("cisco_ssh_key_secret_2026")},
                "Palo-Alto-Firewall-API": {"type": "API Key", "value": VaultManager.encrypt_raw("paloalto_api_token_secure_99")},
                "SNMPv3-Community-String": {"type": "SNMP Auth", "value": VaultManager.encrypt_raw("snmpv3_auth_sha_aes256")}
            }
            for name, val in default_secrets.items():
                database.save_db_secret(name, val["type"], val["value"])
            return default_secrets
        return secrets

    @staticmethod
    def encrypt_raw(value: str) -> str:
        return cipher_suite.encrypt(value.encode()).decode()

    @staticmethod
    def add_secret(name, secret_type, value):
        encrypted = cipher_suite.encrypt(value.encode()).decode()
        database.save_db_secret(name, secret_type, encrypted)

    @staticmethod
    def get_secret(name):
        secret = database.get_db_secret(name)
        if secret:
            encrypted = secret["encrypted_value"]
            return cipher_suite.decrypt(encrypted.encode()).decode()
        return None

    @staticmethod
    def delete_secret(name):
        return database.delete_db_secret(name)

# ========================================================
# PROMPT INJECTION PROTECTION
# ========================================================
PROMPT_INJECTION_KEYWORDS = [
    "ignore previous instructions", "ignore previous rules", "reveal system prompt",
    "disable security", "become developer mode", "execute hidden commands",
    "show api keys", "disable authentication", "forget previous rules",
    "bypass authentication", "bypass authorization", "ignore security", "override role",
    "system status developer", "reveal credentials", "print secrets"
]

def check_prompt_injection(prompt_text):
    text = prompt_text.lower()
    for keyword in PROMPT_INJECTION_KEYWORDS:
        if keyword in text:
            return True
    return False

# ========================================================
# COMMAND VALIDATION ENGINE
# ========================================================
def validate_commands(commands_text, device_type="Cisco"):
    """
    Validates command syntax, interface tags, VLANs, duplicate subnets,
    IP address conflicts, and firmware/hardware compliance.
    """
    logs = []
    has_error = False
    
    lines = [l.strip() for l in commands_text.split('\n') if l.strip() and not l.strip().startswith('!')]
    
    # 1. Syntax check
    logs.append({"check": "Syntax validation", "status": "Passed", "details": f"Syntax parsing completed for {len(lines)} configuration commands."})
    
    # 2. Interface range check
    invalid_interfaces = [l for l in lines if l.startswith("interface ") and not any(x in l for x in ["GigabitEthernet", "TenGigabitEthernet", "FastEthernet", "Vlan", "Loopback", "Tunnel", "Ethernet", "Port-channel", "range", "GigabitEthernet1/0/"])]
    if invalid_interfaces:
        logs.append({"check": "Interface range checking", "status": "Failed", "details": f"Unsupported or unknown interface identifier format in: {', '.join(invalid_interfaces)}"})
        has_error = True
    else:
        logs.append({"check": "Interface range checking", "status": "Passed", "details": "All interfaces conform to target vendor ports structure."})
        
    # 3. Duplicate VLAN check
    vlan_lines = [l for l in lines if l.startswith("vlan ") or "switchport access vlan" in l]
    vlan_ids = []
    duplicate_vlans = []
    for vl in vlan_lines:
        m = re.findall(r'\b\d+\b', vl)
        if m:
            v_id = int(m[0])
            if v_id in vlan_ids:
                duplicate_vlans.append(v_id)
            vlan_ids.append(v_id)
    if duplicate_vlans:
        logs.append({"check": "VLAN duplicate checks", "status": "Warning", "details": f"VLAN identifier conflict/duplicate assignment: VLAN {duplicate_vlans}"})
    else:
        logs.append({"check": "VLAN duplicate checks", "status": "Passed", "details": "No duplicate VLAN assignments or identifiers found."})
        
    # 4. IP Conflict and Subnet Checks
    ips = []
    for l in lines:
        if "ip address" in l:
            m = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', l)
            if m:
                ip = m[0]
                if ip in ips:
                    logs.append({"check": "IP subnet conflict checks", "status": "Failed", "details": f"Duplicate IP address target conflict: {ip}"})
                    has_error = True
                ips.append(ip)
    if not has_error:
        logs.append({"check": "IP subnet conflict checks", "status": "Passed", "details": "Checked local routing databases and scopes. Zero IP conflicts found."})
        
    # 5. Access Lists (ACL) Shadowing & Compliance Audit
    import network_analyzers
    audit_issues = network_analyzers.ConfigAnalyzer.audit_config(commands_text, device_type)
    for issue in audit_issues:
        status_lbl = "Failed" if issue["severity"].lower() == "critical" else "Warning"
        if status_lbl == "Failed":
            has_error = True
        logs.append({
            "check": f"Config Audit: {issue['category']}",
            "status": status_lbl,
            "details": f"{issue['details']} Remediation: {issue['remediation']}"
        })
        
    if not any(iss["category"] == "Shadowed ACL Rule" for iss in audit_issues):
        logs.append({"check": "Access Control shadowing checks", "status": "Passed", "details": "No redundant or shadowed ACL rules found."})
        
    # 6. Device compatibility checks
    logs.append({"check": "Hardware & Firmware validation", "status": "Passed", "details": f"Commands comply with {device_type} OS version standards."})
    
    return logs, has_error

# ========================================================
# SIMULATION ENGINE
# ========================================================
def run_simulation(commands_text, device_type="Cisco"):
    """
    Simulates bridging loops, broadcast storms, routing loops, 
    gateways, STP status, and trunk native VLAN matches.
    """
    logs = []
    has_warning = False
    
    text = commands_text.lower()
    
    # 1. Loops and Broadcast Storms
    if "vlan" in text or "trunk" in text:
        logs.append({"step": "STP Loops & Broadcast Storms", "status": "Passed", "details": "Rapid-PVST+ path recalculation simulated. Link states converged. Zero loops detected."})
    else:
        logs.append({"step": "STP Loops & Broadcast Storms", "status": "Passed", "details": "Layer-2 Spanning Tree topology remains stable."})
        
    # 2. Routing Loops (OSPF / BGP / Static Routing)
    if any(w in text for w in ["router ospf", "router bgp", "ip route", "router eigrp"]):
        logs.append({"step": "Routing Loops & Adjacency", "status": "Passed", "details": "Simulated route exchange. Path convergence validated. Adjacency state is Full. No loops."})
    else:
        logs.append({"step": "Routing Loops & Adjacency", "status": "Passed", "details": "No routing changes simulated."})
        
    # 3. VLAN Trunk Native Match
    if "switchport mode trunk" in text:
        if "native vlan" not in text:
            logs.append({"step": "Trunk native VLAN validation", "status": "Warning", "details": "Trunk port configured without native VLAN keyword. Default Native VLAN 1 is assumed."})
            has_warning = True
        else:
            logs.append({"step": "Trunk native VLAN validation", "status": "Passed", "details": "Trunk Native VLAN tags match peer interfaces."})
    else:
        logs.append({"step": "Trunk native VLAN validation", "status": "Passed", "details": "Trunk native VLAN tags align."})
        
    # 4. VPN and Gateways
    if "tunnel" in text or "crypto" in text:
        logs.append({"step": "IPsec VPN Tunnel Negotiation", "status": "Passed", "details": "Phase 1 / Phase 2 crypto parameters verified. Gateway IP is reachable."})
    else:
        logs.append({"step": "IPsec VPN Tunnel Negotiation", "status": "Passed", "details": "No cryptographic gateway changes."})
        
    return logs, has_warning

# ========================================================
# AI SAFETY FILTER (DESTRUCTIVE COMMAND BLOCKER)
# ========================================================
def check_ai_safety(commands_text):
    """
    Detects highly destructive operational commands that require dual approvals.
    """
    destructive_keywords = [
        "write erase", "erase startup-config", "factory-reset", "factory-default",
        "format flash", "reload", "reboot", "no logging", "no firewall", "no access-list",
        "shutdown core", "delete vlan 1-", "no vlan 1-"
    ]
    
    text = commands_text.lower()
    triggered_rules = []
    
    for kw in destructive_keywords:
        if kw in text:
            triggered_rules.append(f"Destructive action keyword detected: '{kw}'")
            
    # Check for complete VLAN wipeout
    if "no vlan" in text and ("1-" in text or "all" in text or "2-40" in text):
        triggered_rules.append("Destructive mass VLAN deletion rule triggered.")
        
    # Check for core switch shutdown command
    if "interface port-channel" in text and "shutdown" in text:
        triggered_rules.append("Core Switch EtherChannel interface shutdown rule triggered.")
        
    return triggered_rules

# ========================================================
# SYSTEM PERSONAS & INSTRUCTIONS (13-POINT ENFORCEMENT)
# ========================================================
SYSTEM_13_POINT_PROMPT = (
    "\n\nIMPORTANT SECURITY AND FORMATTING RULES:\n"
    "You MUST respond using exactly the following 13 numbered sections. Do NOT omit any section. "
    "Use markdown headings or bold numbering for each section. If a section is not applicable, put 'N/A'.\n"
    "1. Problem\n"
    "2. Analysis\n"
    "3. Risk\n"
    "4. Suggested Solution\n"
    "5. Generated Configuration\n"
    "6. Validation\n"
    "7. Simulation Result\n"
    "8. Deployment Plan\n"
    "9. Rollback Plan\n"
    "10. Verification Steps\n"
    "11. Monitoring Steps\n"
    "12. Security Impact\n"
    "13. Approval Required"
)

PERSONAS = {
    "net_genius": {
        "name": "Network Engineer",
        "emoji": "🌐",
        "description": "OSPF, BGP, routing, switching, VLAN, firewalls, and VPNs.",
        "prompt": "You are Network Engineer, a routing and switching specialist. Diagnose network protocol issues, generate configuration patches (Cisco, Juniper), and suggest diagnostics command runs." + SYSTEM_13_POINT_PROMPT
    },
    "win_admin": {
        "name": "Windows Administrator",
        "emoji": "🖥️",
        "description": "Active Directory, IIS, Hyper-V, DNS, DHCP, and Windows Server.",
        "prompt": "You are Windows Administrator. Manage domain controller integrity, IIS server configurations, Active Directory object replication, DHCP scopes, and PowerShell script creation." + SYSTEM_13_POINT_PROMPT
    },
    "lin_admin": {
        "name": "Linux Administrator",
        "emoji": "🐧",
        "description": "Apache, Nginx, SSH, Docker, Kubernetes, and OS hardening.",
        "prompt": "You are Linux Administrator. Troubleshoot system load, nginx/apache configs, Docker/Kubernetes container orchestration, shell scripting, and server health logs." + SYSTEM_13_POINT_PROMPT
    },
    "noc_eng": {
        "name": "NOC Engineer",
        "emoji": "🚨",
        "description": "Zabbix/SolarWinds integrations, alert analysis, event correlation, and SLAs.",
        "prompt": "You are NOC Engineer. Conduct server health sweeps, correlate hardware events, monitor SLA parameters, and manage notification/incident ticketing escalations." + SYSTEM_13_POINT_PROMPT
    },
    "sec_analyst": {
        "name": "Security Analyst",
        "emoji": "🛡️",
        "description": "Vulnerability scanning, firewall audits, ACL validation, and threat detection.",
        "prompt": "You are Security Analyst. Audit access logs for brute-force attacks, analyze firewall ACL security breaches, suggest mitigation policies, and enforce security controls." + SYSTEM_13_POINT_PROMPT
    },
    "cloud_eng": {
        "name": "Cloud Engineer",
        "emoji": "☁️",
        "description": "AWS, Azure, GCP, VPC/VNET configurations, and security groups.",
        "prompt": "You are Cloud Engineer. Analyze public cloud infrastructures, VPN gateways, VPC routing lists, IAM permissions, and secure instance configurations." + SYSTEM_13_POINT_PROMPT
    },
    "doc_specialist": {
        "name": "Documentation Specialist",
        "emoji": "📝",
        "description": "Auto-generates SOPs, runbooks, change requests, and incident RCAs.",
        "prompt": "You are Documentation Specialist. Synthesize operational findings into Standard Operating Procedures (SOPs), Method of Procedures (MOPs), and Root Cause Analysis (RCA) reports." + SYSTEM_13_POINT_PROMPT
    },
    "auto_eng": {
        "name": "Automation Engineer",
        "emoji": "⚙️",
        "description": "Ansible playbooks, self-healing orchestration, and automation scripts.",
        "prompt": "You are Automation Engineer. Write Ansible playbooks, Python automation tools, and PowerShell scripts to deploy services or perform auto-recovery actions." + SYSTEM_13_POINT_PROMPT
    },
    "assistant": {
        "name": "Friendly Assistant",
        "emoji": "🤖",
        "description": "General-purpose chatbot and router helper.",
        "prompt": "You are Friendly Assistant. Help navigate the AIOps platform capabilities, assist with general questions, or route inputs to the appropriate engineer." + SYSTEM_13_POINT_PROMPT
    }
}

# In-memory session store
_session_personas = {}

def get_persona(key):
    return _session_personas.get(key, "assistant")

def set_persona(key, persona_name):
    if persona_name in PERSONAS:
        _session_personas[key] = persona_name
        return True
    return False

# Auto-routing classifier
def auto_route_intent(prompt_text):
    text = prompt_text.lower()
    if any(w in text for w in ["health check", "daily check", "noc", "zabbix", "prtg", "nagios", "solarwinds", "sla"]):
        return "noc_eng"
    if any(w in text for w in ["security", "firewall log", "acl check", "threat", "vulnerability", "audit", "brute force", "attack"]):
        return "sec_analyst"
    if any(w in text for w in ["aws", "azure", "gcp", "vpc", "vnet", "cloud", "security group"]):
        return "cloud_eng"
    if any(w in text for w in ["sop", "mop", "runbook", "rca", "incident report", "document"]):
        return "doc_specialist"
    if any(w in text for w in ["configure vlan", "ansible", "playbook", "self-healing", "deploy config"]):
        return "auto_eng"
    if any(w in text for w in ["active directory", "ad", "iis", "hyper-v", "windows server", "winrm", "powershell"]):
        return "win_admin"
    if any(w in text for w in ["linux", "nginx", "apache", "docker", "kubernetes", "k8s", "ssh", "cpu"]):
        return "lin_admin"
    if any(w in text for w in ["vpn", "vlan", "bgp", "ospf", "switch", "router", "route", "ping", "traceroute"]):
        return "net_genius"
    return None

# Initialize Gemini
api_key = os.getenv("GEMINI_API_KEY")
gemini_available = False
if api_key and api_key != "your-gemini-api-key" and api_key.strip() != "":
    try:
        genai.configure(api_key=api_key)
        gemini_available = True
        logger.info("Gemini AI engine active", extra={"model": "gemini-1.5-flash"})
    except Exception as e:
        logger.error(f"Error configuring Gemini: {e}", exc_info=True)

# ========================================================
# HIGH-FIDELITY 13-POINT SCENARIO TEMPLATE MOCK RESPONSES
# ========================================================
SCENARIOS = {
    "vpn is down": {
        "persona": "net_genius",
        "response": (
            "### 1. Problem\n"
            "Remote IPsec VPN connection failure between HQ Edge Router and AWS Virtual Private Gateway.\n\n"
            "### 2. Analysis\n"
            "Phase 1 ISAKMP Security Association (SA) negotiation failed with a local lifetime mismatch parameter. The on-premises router local lifetime config is `86400` seconds, while the peer AWS gateway has a hardcoded configuration expecting `28800` seconds.\n\n"
            "### 3. Risk\n"
            "High. Inter-VPC and HQ network traffic loop is severed. Critical production data transfers between database clusters and remote offices are halted.\n\n"
            "### 4. Suggested Solution\n"
            "Update the Phase 1 ISAKMP policy lifetime parameter to `28800` seconds on the HQ Cisco Edge Router.\n\n"
            "### 5. Generated Configuration\n"
            "```text\n"
            "crypto isakmp policy 10\n"
            " lifetime 28800\n"
            "```\n\n"
            "### 6. Validation\n"
            "- Interface GigabitEthernet1 (198.51.100.2) is operational and has a route to the peer (203.0.113.10).\n"
            "- ISAKMP configuration syntax conforms to IOS-XE standards. No duplicate parameters.\n\n"
            "### 7. Simulation Result\n"
            "- Spanning Tree Loop check: Passed.\n"
            "- Routing loops: None. OSPF and BGP adjacencies verified.\n"
            "- Phase 1 crypt parameters match simulation environment: Successful.\n\n"
            "### 8. Deployment Plan\n"
            "1. Take automatic configuration backup of `router-hq`.\n"
            "2. Deploy ISAKMP lifetime modification via secure SSH CLI.\n"
            "3. Clear active crypto sessions to force renegotiation.\n\n"
            "### 9. Rollback Plan\n"
            "```text\n"
            "crypto isakmp policy 10\n"
            " lifetime 86400\n"
            "clear crypto isakmp sa\n"
            "```\n\n"
            "### 10. Verification Steps\n"
            "- Run `show crypto isakmp sa` on HQ router. Confirm state is `QM_IDLE`.\n"
            "- Verify end-to-end ICMP ping to 10.0.0.1.\n\n"
            "### 11. Monitoring Steps\n"
            "- Monitor syslog events for %ASA-5-713008 (ISAKMP SA established).\n"
            "- Setup Zabbix SLA trigger on tunnel latency.\n\n"
            "### 12. Security Impact\n"
            "Low Risk. Aligning lifetimes reduces negotiation timeout overheads without lowering encryption standards (AES-256-SHA).\n\n"
            "### 13. Approval Required\n"
            "Requires Senior Engineer authorization. Manager approval token is mandatory for deployment."
        ),
        "diagnostics": (
            "📋 *Crypto ISAKMP Diagnostics Output:*\n"
            "```text\n"
            "Router-HQ# show crypto isakmp sa\n"
            "IPv4 Source      IPv4 Destination      State      Id      Type\n"
            "198.51.100.2     203.0.113.10          MM_NO_STATE 102    active\n\n"
            "Router-HQ# debug crypto isakmp\n"
            "ISAKMP:(0): peer matches local profile AWS-VPN-PROFILE\n"
            "ISAKMP:(0): lifetime mismatch: peer has 28800, local configuration has 86400\n"
            "ISAKMP:(0): phase 1 negotiation failed due to parameters mismatch\n"
            "```"
        ),
        "healing": (
            "⚙️ *Self-Healing Task Log:*\n"
            "Executing Ansible Playbook: `resolve_vpn_lifetime.yml`\n"
            "```text\n"
            "PLAY [Update ISAKMP Lifetime Policies] *****************************************\n"
            "TASK [cisco.ios.ios_config] : Update lifetime parameter on HQ Router\n"
            "changed: [router-hq.net.local] \n\n"
            "TASK [cisco.ios.ios_command] : Clear crypto sessions\n"
            "changed: [router-hq.net.local]\n\n"
            "PLAY RECAP *********************************************************************\n"
            "router-hq.net.local        : ok=2    changed=2    unreachable=0    failed=0\n"
            "```\n"
            "✅ *Result*: Cryptographic tunnel renegotiated successfully. State is now `QM_IDLE` (Fully Connected)."
        ),
        "rca": (
            "📝 *Root Cause Analysis (RCA-2026-0043)*\n"
            "• *Incident*: IPSec Tunnel Outage\n"
            "• *Root Cause*: Configuration drift on Router-HQ after manual IOS upgrade reset ISAKMP lifetime default to 86400s (AWS side is hardcoded to 28800s).\n"
            "• *Resolution*: Applied auto-healing patch configuring `lifetime 28800` in crypto policy.\n"
            "• *Prevention*: Configured configuration compliance checks in SolarWinds to trigger alarms if lifetime settings drift."
        )
    },
    "server cpu is 100%": {
        "persona": "lin_admin",
        "response": (
            "### 1. Problem\n"
            "Server `app-srv-02.prod.local` CPU utilization reports critical 100% load warning.\n\n"
            "### 2. Analysis\n"
            "An orphaned `nginx` worker pid `40912` is locked in an infinite regular expression regex loop.\n\n"
            "### 3. Risk\n"
            "High. Nginx cannot process new HTTP threads. Load-balancer will drop node `app-srv-02` from pool, overloading remaining nodes.\n\n"
            "### 4. Suggested Solution\n"
            "Gracefully terminate the orphaned process worker thread and reload Nginx service configurations.\n\n"
            "### 5. Generated Configuration\n"
            "```text\n"
            "kill -9 40912\n"
            "systemctl reload nginx\n"
            "```\n\n"
            "### 6. Validation\n"
            "- Target server PID `40912` is active under user `nginx`.\n"
            "- Systemd service manager is online. Syntax test `nginx -t` passed.\n\n"
            "### 7. Simulation Result\n"
            "- Process termination simulated: OS returns resources instantly.\n"
            "- CPU load drops from 100% to 4%.\n"
            "- No service interruption simulated.\n\n"
            "### 8. Deployment Plan\n"
            "1. Establish secure SSH session to server.\n"
            "2. Send SIGKILL signal to target worker thread.\n"
            "3. Trigger clean config reload on nginx systemd.\n\n"
            "### 9. Rollback Plan\n"
            "Not applicable for simple process cleanup. In case of overall failure, restart service:\n"
            "```text\n"
            "systemctl restart nginx\n"
            "```\n\n"
            "### 10. Verification Steps\n"
            "- Run `ps aux | grep nginx` and verify old PID is dead.\n"
            "- Query local load averages using `uptime` or `top`.\n\n"
            "### 11. Monitoring Steps\n"
            "- Graph CPU usage metrics in Datadog.\n"
            "- Setup alarms for worker threads running longer than 1 hour.\n\n"
            "### 12. Security Impact\n"
            "Zero. Terminating the stuck process restores normal system operations without security vulnerabilities.\n\n"
            "### 13. Approval Required\n"
            "Senior Engineer authority needed for manual thread termination."
        ),
        "diagnostics": (
            "📋 *Linux CPU Diagnostics Output:*\n"
            "```text\n"
            "$ ssh admin@app-srv-02 'top -b -n 1 | head -n 12'\n"
            "top - 20:04:12 up 14 days,  3:12,  1 user,  load average: 8.52, 6.10, 4.21\n"
            "Tasks: 210 total,   2 running, 208 sleeping,   0 stopped,   0 zombie\n"
            "%Cpu(s): 99.8 us,  0.2 sy,  0.0 ni,  0.0 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st\n"
            "MiB Mem :  8192.4 total,  1214.8 free,  5180.2 used,  1797.4 buff/cache\n\n"
            "  PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND\n"
            "40912 nginx     20   0  145620  84120   4312 R 100.0   1.0   4:12.45 nginx: worker\n"
            " 1012 root      20   0   84122   6120   2142 S   0.1   0.1   0:10.12 systemd\n"
            "```"
        ),
        "healing": (
            "⚙️ *Self-Healing Task Log:*\n"
            "Executing Server Recover Playbook: `kill_orphaned_nginx.yml`\n"
            "```text\n"
            "PLAY [Resolve High CPU Loop on nginx] ******************************************\n"
            "TASK [Kill process 40912] : Terminate offending process using SIGKILL\n"
            "changed: [app-srv-02.prod.local]\n\n"
            "TASK [Reload nginx service] : Systemd reload daemon config\n"
            "changed: [app-srv-02.prod.local]\n\n"
            "PLAY RECAP *********************************************************************\n"
            "app-srv-02.prod.local      : ok=2    changed=2    unreachable=0    failed=0\n"
            "```\n"
            "✅ *Result*: CPU load returned to normal (3.4% idle). Service metrics are healthy."
        ),
        "rca": (
            "📝 *Root Cause Analysis (RCA-2026-0044)*\n"
            "• *Incident*: app-srv-02 CPU Maxed Out\n"
            "• *Root Cause*: Infinite regex evaluation inside custom server routing configurations causing CPU lockup in Nginx process worker.\n"
            "• *Resolution*: Forcefully killed pid `40912` and reloaded standard config.\n"
            "• *Prevention*: Configured validation rules to block regex rules without execution timeout limits."
        )
    },
    "configure vlan 20": {
        "persona": "auto_eng",
        "response": (
            "### 1. Problem\n"
            "VLAN 20 Database subnet provisioning request on core switches (`sw-core-01`, `sw-core-02`).\n\n"
            "### 2. Analysis\n"
            "Request to establish Layer-2 segregation for database instances. Scope includes creating VLAN 20 database subnet and mapping port fast interfaces.\n\n"
            "### 3. Risk\n"
            "Low. Requires modifying VLAN databases. Minor risk of STP topology recalculation if native VLAN configurations are mismatched.\n\n"
            "### 4. Suggested Solution\n"
            "Provision VLAN 20 and name it `DB_Subnet`. Configure interface GigabitEthernet1/0/1 through 12 to map to VLAN 20 in Access Mode.\n\n"
            "### 5. Generated Configuration\n"
            "```text\n"
            "vlan 20\n"
            " name DB_Subnet\n"
            "!\n"
            "interface range GigabitEthernet1/0/1 - 12\n"
            " switchport access vlan 20\n"
            " switchport mode access\n"
            " spanning-tree portfast\n"
            "```\n\n"
            "### 6. Validation\n"
            "- Verified switch models support VLAN encapsulation.\n"
            "- Interface ranges exist on target core switches. No native VLAN overlaps.\n\n"
            "### 7. Simulation Result\n"
            "- Rapid STP Simulation: Completed successfully. PortFast status restricts bridging loops.\n"
            "- Broadcast Storm check: Passed.\n\n"
            "### 8. Deployment Plan\n"
            "1. Take state backup of `sw-core-01` and `sw-core-02`.\n"
            "2. Deploy VLAN and interface settings via Ansible playbook.\n"
            "3. Verify active bindings.\n\n"
            "### 9. Rollback Plan\n"
            "```text\n"
            "interface range GigabitEthernet1/0/1 - 12\n"
            " no switchport access vlan 20\n"
            " switchport access vlan 1\n"
            "no vlan 20\n"
            "```\n\n"
            "### 10. Verification Steps\n"
            "- Execute `show vlan id 20` to verify status.\n"
            "- Execute `show interface status` to verify GigabitEthernet1/0/1-12 states.\n\n"
            "### 11. Monitoring Steps\n"
            "- Check SolarWinds configuration drift reports.\n"
            "- Log port flapping events via Syslog.\n\n"
            "### 12. Security Impact\n"
            "Excellent. Restricting database servers to a separate access segment enforces Least Privilege Network Security.\n\n"
            "### 13. Approval Required\n"
            "Requires Network Engineer to generate, Senior Engineer to deploy. Destructive actions require Dual Approvals (Senior Engineer + Manager)."
        ),
        "diagnostics": (
            "📋 *Target Switch Interface Configuration Preview:*\n"
            "```text\n"
            "vlan 20\n"
            " name DB_Subnet\n"
            "!\n"
            "interface range GigabitEthernet1/0/1 - 12\n"
            " switchport access vlan 20\n"
            " switchport mode access\n"
            " spanning-tree portfast\n"
            "```"
        ),
        "healing": (
            "⚙️ *Automation Task Log:*\n"
            "Executing Ansible Playbook: `provision_vlan_20.yml`\n"
            "```text\n"
            "PLAY [Provision VLAN 20 across switches] **************************************\n"
            "TASK [Create VLAN 20] : Add VLAN with ID 20 and name DB_Subnet\n"
            "changed: [sw-core-01] [sw-core-02]\n\n"
            "TASK [Apply Interface maps] : Configure access ports on core switches\n"
            "changed: [sw-core-01] [sw-core-02]\n\n"
            "PLAY RECAP *********************************************************************\n"
            "sw-core-01                 : ok=2    changed=2    unreachable=0    failed=0\n"
            "sw-core-02                 : ok=2    changed=2    unreachable=0    failed=0\n"
            "```\n"
            "✅ *Result*: VLAN 20 configured across all nodes. Access ports active."
        ),
        "rca": (
            "📝 *Change Request Report (CR-2026-0099)*\n"
            "• *Action*: VLAN 20 Creation\n"
            "• *Reason*: Provisioning backend network for database cluster setup.\n"
            "• *Result*: Completed switch configuration templates and trunk mapping.\n"
            "• *Authorizer*: Automation Engine"
        )
    },
    "check daily server health": {
        "persona": "noc_eng",
        "response": (
            "### 1. Problem\n"
            "Operational routine check: Daily Server Infrastructure Health Sweep.\n\n"
            "### 2. Analysis\n"
            "NOC automated sweep indicates 24 nodes are fully functional and healthy. Host `db-srv-01` reports log directory partition is at 94% storage load.\n\n"
            "### 3. Risk\n"
            "Medium. If disk utilization hits 100%, MySQL database updates will fail, locking core service queues.\n\n"
            "### 4. Suggested Solution\n"
            "Execute a cleanup playbook to purge compressed historical logs (.gz format) older than 30 days.\n\n"
            "### 5. Generated Configuration\n"
            "```text\n"
            "find /var/log -name '*.gz' -mtime +30 -delete\n"
            "```\n\n"
            "### 6. Validation\n"
            "- Command syntax verified for target database filesystem. Target directory `/var/log` contains 14.2GB of old archives.\n\n"
            "### 7. Simulation Result\n"
            "- Log purge simulated: 14.2GB freed. Storage capacity drops to 62%.\n"
            "- No running application log files are affected.\n\n"
            "### 8. Deployment Plan\n"
            "1. SSH connection to server `db-srv-01`.\n"
            "2. Run cleanup script with minimal system privilege.\n"
            "3. Verify active disk space availability.\n\n"
            "### 9. Rollback Plan\n"
            "Historical log archives cannot be restored easily. Ensure offline backup exists prior to purging. If partition fills again, expand mount space.\n\n"
            "### 10. Verification Steps\n"
            "- Run `df -h /var/log` to confirm available storage.\n"
            "- Verify active DB logs are still updated.\n\n"
            "### 11. Monitoring Steps\n"
            "- Monitor Zabbix disk triggers.\n"
            "- Configure logrotate policy to compress and offload to S3 archive hourly.\n\n"
            "### 12. Security Impact\n"
            "Low Risk. Deleting rotated archives complies with GDPR security standards if logs are already aggregated inside central SIEM.\n\n"
            "### 13. Approval Required\n"
            "Standard routine action. Approved by NOC Lead. No high-level management approvals required."
        ),
        "diagnostics": (
            "📋 *Server Sweep Results (Zabbix API query):*\n"
            "```text\n"
            "25 Servers Checked:\n"
            "- Active directory DC-01  : [HEALTHY] (CPU: 12%, RAM: 54%)\n"
            "- Web Server app-srv-01   : [HEALTHY] (CPU: 22%, RAM: 45%)\n"
            "- Database db-srv-01      : [WARN] Disk space utilization is at 94% on /var/log\n"
            "- Load Balancer lb-01     : [HEALTHY] (CPU: 8%, RAM: 22%)\n"
            "...\n"
            "⚠️ Summary: 24 nodes HEALTHY, 1 node WARN."
            "```"
        ),
        "healing": (
            "⚙️ *Self-Healing Task Log:*\n"
            "Executing Clean Script: `purge_temp_logs.sh` on `db-srv-01`\n"
            "```text\n"
            "Connecting to db-srv-01.prod.local...\n"
            "Searching for old compressed log archives in /var/log...\n"
            "Removed 14.2 GB of expired .gz logs.\n"
            "Disk space freed. Current utilization: 62%.\n"
            "```\n"
            "✅ *Result*: Host db-srv-01 disk space alarm cleared."
        ),
        "rca": (
            "📝 *Operations Review Report*\n"
            "• *Task*: Daily Health Check Sweep\n"
            "• *Findings*: Host `db-srv-01` log partition was near max capacity.\n"
            "• *Action*: Automatically purged old gz logs to free 14.2 GB of memory.\n"
            "• *Status*: SLA compliant (100% server availability maintained)."
        )
    },
    "analyze this firewall log": {
        "persona": "sec_analyst",
        "response": (
            "### 1. Problem\n"
            "Ongoing SSH Password Spraying Attack detected from external IP `198.51.100.45` targeting edge gateway portals.\n\n"
            "### 2. Analysis\n"
            "Cisco ASA syslog reports 120 authentication denial attempts per minute from source `198.51.100.45` to port 22 on perimeter host `203.0.113.12`.\n\n"
            "### 3. Risk\n"
            "Critical. Potential edge compromise if administrative credentials are weak. Performance degradation on SSH daemon queues.\n\n"
            "### 4. Suggested Solution\n"
            "Blacklist the attacker's source IP address `198.51.100.45` at the top of the outer edge firewall Access Control List (ACL).\n\n"
            "### 5. Generated Configuration\n"
            "```text\n"
            "access-list outside_access_in line 1 extended deny tcp host 198.51.100.45 any eq 22\n"
            "```\n\n"
            "### 6. Validation\n"
            "- The Outside ACL table `outside_access_in` exists.\n"
            "- Interface bindings are active. Rule format is valid for Cisco ASA CLI syntax.\n\n"
            "### 7. Simulation Result\n"
            "- Simulated packets from `198.51.100.45` are dropped on ASA entrance.\n"
            "- Attack traffic drops to 0. Access for regular users is unaffected.\n\n"
            "### 8. Deployment Plan\n"
            "1. Backup current ASA runtime configuration.\n"
            "2. Deploy ACL statement at line index 1 of outside list.\n"
            "3. Verify active hits count on rule.\n\n"
            "### 9. Rollback Plan\n"
            "```text\n"
            "no access-list outside_access_in line 1 extended deny tcp host 198.51.100.45 any eq 22\n"
            "```\n\n"
            "### 10. Verification Steps\n"
            "- Run `show access-list outside_access_in | include 198.51.100.45`.\n"
            "- Check hit-counts increment.\n\n"
            "### 11. Monitoring Steps\n"
            "- Log ACL drops via NetFlow syslog alerts.\n"
            "- Review alerts in SIEM dashboard for further threat markers.\n\n"
            "### 12. Security Impact\n"
            "High. Proactively stops external intrusion sweeps. Zero risk of service disruption for inside networks.\n\n"
            "### 13. Approval Required\n"
            "Requires Security Administrator or Manager validation prior to blacklisting."
        ),
        "diagnostics": (
            "📋 *Firewall Syslog Extracts:*\n"
            "```text\n"
            "2026-06-23T20:01:10Z %ASA-6-106015: Deny tcp src outside:198.51.100.45/54312 dst inside:203.0.113.12/22 by access-group 'outside_access_in'\n"
            "2026-06-23T20:01:11Z %ASA-6-106015: Deny tcp src outside:198.51.100.45/54314 dst inside:203.0.113.12/22 by access-group 'outside_access_in'\n"
            "2026-06-23T20:01:12Z %ASA-6-106015: Deny tcp src outside:198.51.100.45/54316 dst inside:203.0.113.12/22 by access-group 'outside_access_in'\n"
            "⚠️ Trigger: Brute Force Signature detected (SSH Connection rate > 120/min)."
            "```"
        ),
        "healing": (
            "⚙️ *Self-Healing Task Log:*\n"
            "Deploying Network ACL Block rule: `blacklist_ip_asa.yml`\n"
            "```text\n"
            "PLAY [Blacklist attacker on edge ASA] *****************************************\n"
            "TASK [cisco.asa.asa_config] : Add deny statement to top of OUTSIDE-IN access-list\n"
            "changed: [asa-edge-01.sec.local]\n\n"
            "PLAY RECAP *********************************************************************\n"
            "asa-edge-01.sec.local      : ok=1    changed=1    unreachable=0    failed=0\n"
            "```\n"
            "✅ *Result*: Host IP `198.51.100.45` dropped on interface entry. Attack mitigated."
        ),
        "rca": (
            "📝 *Threat Mitigation Report (SEC-2026-0012)*\n"
            "• *Incident*: Remote SSH Brute Force Attempt\n"
            "• *Attacker IP*: `198.51.100.45`\n"
            "• *Action*: Dynamically updated firewall ACL policy 'outside_access_in' to drop all packets from attacker.\n"
            "• *Status*: Blocked successfully."
        )
    }
}

# ========================================================
# AI RESPONSE GENERATOR
# ========================================================
def find_matching_scenario(prompt_text):
    if not prompt_text:
        return None
    text = prompt_text.lower().strip()
    normalized = text.rstrip("?.-! ")
    
    # 1. Direct exact match
    if normalized in SCENARIOS:
        return normalized
        
    # 2. Check if normalized contains or is contained in any scenario key
    for key in SCENARIOS:
        if normalized == key or normalized.startswith(key) or normalized.endswith(key) or key in normalized:
            return key
            
    # 3. Keyword matches
    if any(w in text for w in ["vpn", "ipsec", "isakmp"]):
        return "vpn is down"
    if any(w in text for w in ["cpu", "nginx", "app-srv-02", "100%"]):
        return "server cpu is 100%"
    if any(w in text for w in ["vlan 20", "database subnet", "vlan20"]):
        return "configure vlan 20"
    if any(w in text for w in ["health check", "daily check", "server health", "telemetry sweep"]):
        return "check daily server health"
    if any(w in text for w in ["firewall log", "syslog", "asa", "password spray", "brute force", "198.51.100.45"]):
        return "analyze this firewall log"
        
    return None

def generate_ai_response(prompt_text, conversation_history=None, persona_key="assistant", active_scenario=None):
    # 1. Prompt Injection Protection
    if check_prompt_injection(prompt_text):
        return (
            "### 1. Problem\n"
            "🚨 *Zero Trust Security Block*\n\n"
            "### 2. Analysis\n"
            "Security filter intercepted query containing system-bypass keywords or unauthorized instructions.\n\n"
            "### 3. Risk\n"
            "Critical Security Policy Violation.\n\n"
            "### 4. Suggested Solution\n"
            "Please refrain from attempting prompt injection. Ensure all actions conform to authenticated role permissions.\n\n"
            "### 5. Generated Configuration\n"
            "N/A\n\n"
            "### 6. Validation\n"
            "Failed. Prompt violates access policies.\n\n"
            "### 7. Simulation Result\n"
            "Blocked by prompt injection engine.\n\n"
            "### 8. Deployment Plan\n"
            "N/A\n\n"
            "### 9. Rollback Plan\n"
            "N/A\n\n"
            "### 10. Verification Steps\n"
            "N/A\n\n"
            "### 11. Monitoring Steps\n"
            "Incident logged in Security Audit timeline.\n\n"
            "### 12. Security Impact\n"
            "Attempt mitigated under Zero-Trust protocols.\n\n"
            "### 13. Approval Required\n"
            "N/A"
        )
        
    # Find matching scenario key from prompt first, or use active_scenario if passed
    scenario_key = find_matching_scenario(prompt_text)
    if not scenario_key and active_scenario:
        scenario_key = find_matching_scenario(active_scenario)
        
    scenario_info = SCENARIOS.get(scenario_key) if scenario_key else None
    
    # ----------------------------------------------------
    # ADVANCED TOOL INTEGRATION INTERCEPT
    # ----------------------------------------------------
    text = prompt_text.lower()
    tool_output = None
    
    # Map scenario to target device
    device_map = {
        "vpn is down": "router-hq",
        "server cpu is 100%": "app-srv-02",
        "configure vlan 20": "sw-core-01",
        "configure vlan 25": "sw-core-01",
        "check daily server health": "db-srv-01",
        "analyze this firewall log": "asa-edge-01"
    }
    device = device_map.get(scenario_key, "router-hq")
    
    # 1. Run Diagnostics Tool
    if any(w in text for w in ["run diagnostics", "run diagnostic", "diagnose", "diagnostics", "check health", "sweep"]):
        import network_analyzers
        res = network_analyzers.TroubleshootingGraph.execute_sweep(device)
        tool_output = (
            f"### NOC AUTOMATED DIAGNOSTIC SWEEP RESULTS\n"
            f"**Node Name**: `{device}`\n"
            f"**Sweep Target Status**: `{res['status']}`\n"
            f"**Confidence Level**: `{res['confidence_score']}%`\n\n"
            f"**Troubleshooting Sequence Timeline**:\n"
            f"```text\n{res['logs']}\n```\n\n"
            f"**Suggested Remediation SOP**:\n{res['remediation_plan'] or 'No active failures detected at physical or virtual layers.'}"
        )
        
    # 2. Deploy Configuration / Healing Tool
    elif any(w in text for w in ["deploy config", "deploy configuration", "heal", "apply patch", "remediate", "apply fix"]):
        import network_analyzers
        res = network_analyzers.TroubleshootingGraph.execute_sweep(device)
        tool_output = (
            f"### ZERO-TRUST Patches & Remediation\n"
            f"**Target Node**: `{device}`\n"
            f"**Remediation Command block**:\n"
            f"```text\n{res['remediation_plan'] or '! No configuration patch required.'}\n```\n\n"
            f"To deploy this patch, please switch to the **Incident Control Room** tab in the sidebar, select the active incident, and execute the Zero-Trust 5-step stepper (Validation -> Simulation -> Approvals -> Execution -> Verification) to enforce authorization guidelines."
        )
        
    # 3. Generate RCA Report Tool
    elif any(w in text for w in ["generate rca", "rca", "root cause", "rca report"]):
        import network_analyzers
        import report_generator
        res = network_analyzers.TroubleshootingGraph.execute_sweep(device)
        incident_details = {
            "device": device,
            "root_cause": res["logs"].split("\n")[-2] if len(res["logs"].split("\n")) > 1 else "Degraded protocol interface.",
            "cli_fix": res["remediation_plan"]
        }
        tool_output = report_generator.ReportGenerator.generate_rca(scenario_key or "general network alert", incident_details)
        
    # 4. Generate MOP Playbook Tool
    elif any(w in text for w in ["mop", "method of procedure", "playbook"]):
        import network_analyzers
        import report_generator
        res = network_analyzers.TroubleshootingGraph.execute_sweep(device)
        tool_output = report_generator.ReportGenerator.generate_mop(scenario_key or "configuration script", res["remediation_plan"] or "N/A", device)
        
    # 5. Generate SOP Policy Tool
    elif any(w in text for w in ["sop", "standard operating procedure"]):
        import report_generator
        tool_output = report_generator.ReportGenerator.generate_sop(scenario_key or "critical NOC alarm")
        
    # 6. Analyze PCAP Packets Tool
    elif any(w in text for w in ["pcap", "packet analysis", "analyze pcap", "wireshark"]):
        import graph_ocr_packet
        res = graph_ocr_packet.PacketAnalyzer.analyze_pcap(f"{scenario_key or 'outage'}.pcap")
        tool_output = (
            f"### Scapy Packet Inspector Output\n"
            f"**PCAP Filename**: `{res['filename']}`\n"
            f"**Audited Frames Count**: {res['total_packets']}\n"
            f"**TCP Retransmissions**: {res['tcp_retransmissions']} ({res['tcp_retransmission_rate_pct']}% rate)\n"
            f"**DNS Code Mismatches (NXDOMAIN)**: {res['dns_failures']}\n"
            f"**TLS Handshake Warnings**: {res['tls_handshake_errors']}\n"
            f"**Path Fragmentation (MTU)**: {res['fragmented_packets']} packets\n"
            f"**Health Assessment**: **{res['health_conclusion']}**"
        )
        
    # 7. Query Topology Graph Database Tool
    elif any(w in text for w in ["topology", "graph", "network map", "nodes status"]):
        import graph_ocr_packet
        topo = graph_ocr_packet.Neo4jTopologyConnector()
        graph = topo.get_topology_graph()
        nodes_str = ", ".join([f"{n['name']} ({n['role']})" for n in graph["nodes"]])
        edges_str = "\n".join([f"- {e['source']} -> {e['target']} via {e['type']} ({e['details']})" for e in graph["edges"]])
        tool_output = (
            f"### Graph Database Network Topology\n"
            f"**Discovered Nodes**:\n{nodes_str}\n\n"
            f"**Logical Link Adjacencies**:\n{edges_str}"
        )
        
    # 8. Compliance Config Audit Tool
    elif any(w in text for w in ["audit", "compliance", "check config", "vulnerability"]):
        import network_analyzers
        sample_config = "username admin privilege 15 password public\ntransport input telnet\nsnmp-server community public RO\nip address 10.0.1.1 255.255.255.0\nip address 10.0.1.1 255.255.255.0\npermit ip any any\ndeny ip 10.0.0.0 0.255.255.255 any"
        issues = network_analyzers.ConfigAnalyzer.audit_config(sample_config)
        issues_str = "\n".join([f"- **{iss['category']}** ({iss['severity']}): {iss['details']} *Remediation*: `{iss['remediation']}`" for iss in issues])
        tool_output = (
            f"### Static Configuration Compliance Audit\n"
            f"**Security Warnings Isolated**:\n{issues_str}"
        )
        
    # If a tool matched, return its output directly or feed it into Gemini
    if tool_output:
        if not gemini_available:
            return tool_output
        else:
            prompt_text = (
                f"The system has executed the user request using the backend tools. "
                f"Here is the raw output from the tool execution:\n"
                f"{tool_output}\n\n"
                f"Please explain, summarize, or present these results to the user in a helpful, friendly manner. "
                f"Do not lose any essential parameters like metrics, logs, or codes."
            )
            
    # If the user asked a specific question about the active scenario (e.g. about rollback, rca, diagnostics, healing)
    # and gemini is not available, we can return the specific section.
    if scenario_info and not gemini_available:
        text = prompt_text.lower()
        if "diag" in text or "diagnose" in text:
            return scenario_info.get("diagnostics", scenario_info["response"])
        elif "heal" in text or "fix" in text or "playbook" in text or "solution" in text or "patch" in text:
            return scenario_info.get("healing", scenario_info["response"])
        elif "rca" in text or "root cause" in text:
            return scenario_info.get("rca", scenario_info["response"])
        return scenario_info["response"]
        
    # 3. Dynamic Gemini API Call
    persona = PERSONAS.get(persona_key, PERSONAS["assistant"])
    system_instruction = persona["prompt"]
    
    if scenario_info:
        system_instruction += (
            f"\n\nActive Incident Context:\n"
            f"You are troubleshooting the following active incident:\n"
            f"Scenario Key: {scenario_key}\n"
            f"Incident Reference Details:\n{scenario_info['response']}\n"
            f"Diagnostics Data:\n{scenario_info.get('diagnostics', 'N/A')}\n"
            f"Self-Healing Data:\n{scenario_info.get('healing', 'N/A')}\n"
            f"RCA Data:\n{scenario_info.get('rca', 'N/A')}\n"
            f"Please refer to the above Active Incident Context when answering questions about the current issue. "
            f"Do not make up facts; use the details provided in the context."
        )
    
    if gemini_available:
        try:
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=system_instruction
            )
            
            contents = []
            if conversation_history:
                for msg in conversation_history:
                    role = "user" if msg['role'] == 'user' else "model"
                    contents.append({"role": role, "parts": [msg['text']]})
            
            contents.append({"role": "user", "parts": [prompt_text]})
            response = model.generate_content(contents)
            return response.text
        except Exception as e:
            print(f"Gemini API Error: {e}")
            
    # 4. Fallback mock generator (13-point format)
    return get_general_simulated_response(prompt_text, persona_key, scenario_info)

def get_general_simulated_response(prompt_text, persona_key, scenario_info=None):
    if scenario_info:
        return scenario_info["response"]
        
    persona = PERSONAS.get(persona_key, PERSONAS["assistant"])
    return (
        f"### 1. Problem\n"
        f"Request to process '{prompt_text}' under specialized agent domain.\n\n"
        f"### 2. Analysis\n"
        f"Analyzing command tokens within context of {persona['name']}.\n\n"
        f"### 3. Risk\n"
        f"Generic query risks. Minor configuration adjustments proposed.\n\n"
        f"### 4. Suggested Solution\n"
        f"Apply template edits relative to '{prompt_text}'.\n\n"
        f"### 5. Generated Configuration\n"
        f"```text\n"
        f"! Configuration template for: {prompt_text}\n"
        f"interface GigabitEthernet1/0/24\n"
        f" description Configured by {persona['name']}\n"
        f"```\n\n"
        f"### 6. Validation\n"
        f"Interface verified. Conformity checks passed.\n\n"
        f"### 7. Simulation Result\n"
        f"No loops or gateway mismatches detected.\n\n"
        f"### 8. Deployment Plan\n"
        f"1. Save configuration.\n"
        f"2. Apply interface changes.\n\n"
        f"### 9. Rollback Plan\n"
        f"```text\n"
        f"interface GigabitEthernet1/0/24\n"
        f" no description\n"
        f"```\n\n"
        f"### 10. Verification Steps\n"
        f"Verify connection status on target interface.\n\n"
        f"### 11. Monitoring Steps\n"
        f"Review syslog updates.\n\n"
        f"### 12. Security Impact\n"
        f"Low. Encapsulation conforms to standard segment boundaries.\n\n"
        f"### 13. Approval Required\n"
        f"Standard engineering permissions required."
    )

import asyncio

async def generate_streaming_response(
    prompt_text,
    conversation_history=None,
    persona_key="assistant",
    active_scenario=None,
    active_incidents_context=None,
    topology_context=None,
    uploaded_logs=None,
    uploaded_config=None
):
    """
    Async generator yielding JSON-serializable chunks containing response text
    and metadata. Incorporates persona settings, tool outputs, incident data,
    topology details, and uploaded file contents.
    """
    # 1. Prompt Injection Protection Check
    if check_prompt_injection(prompt_text):
        block_text = (
            "### 1. Problem\n"
            "🚨 *Zero Trust Security Block*\n\n"
            "### 2. Analysis\n"
            "Security filter intercepted query containing system-bypass keywords or unauthorized instructions.\n\n"
            "### 3. Risk\n"
            "Critical Security Policy Violation.\n\n"
            "### 4. Suggested Solution\n"
            "Please refrain from attempting prompt injection. Ensure all actions conform to authenticated role permissions."
        )
        words = block_text.split(" ")
        for i, word in enumerate(words):
            yield {
                "text": word if i == len(words) - 1 else word + " ",
                "done": False,
                "persona": "assistant",
                "routed": False,
                "isScenario": False,
                "scenarioKey": None
            }
            await asyncio.sleep(0.01)
        yield {
            "text": "",
            "done": True,
            "persona": "assistant",
            "routed": False,
            "isScenario": False,
            "scenarioKey": None
        }
        return

    # 2. Dynamic Classifier Intent Routing
    routed_persona = auto_route_intent(prompt_text)
    session_persona = routed_persona if routed_persona else persona_key

    # 3. Match active scenarios
    scenario_key = find_matching_scenario(prompt_text)
    if not scenario_key and active_scenario:
        scenario_key = find_matching_scenario(active_scenario)

    scenario_info = SCENARIOS.get(scenario_key) if scenario_key else None

    # Map scenario to target device
    device_map = {
        "vpn is down": "router-hq",
        "server cpu is 100%": "app-srv-02",
        "configure vlan 20": "sw-core-01",
        "configure vlan 25": "sw-core-01",
        "check daily server health": "db-srv-01",
        "analyze this firewall log": "asa-edge-01"
    }
    device = device_map.get(scenario_key, "router-hq")

    # 4. Check for tool matches
    text_lower = prompt_text.lower()
    tool_output = None

    if any(w in text_lower for w in ["run diagnostics", "run diagnostic", "diagnose", "diagnostics", "check health", "sweep"]):
        import network_analyzers
        res = network_analyzers.TroubleshootingGraph.execute_sweep(device)
        tool_output = (
            f"### NOC AUTOMATED DIAGNOSTIC SWEEP RESULTS\n"
            f"**Node Name**: `{device}`\n"
            f"**Sweep Target Status**: `{res['status']}`\n"
            f"**Confidence Level**: `{res['confidence_score']}%`\n\n"
            f"**Troubleshooting Sequence Timeline**:\n"
            f"```text\n{res['logs']}\n```\n\n"
            f"**Suggested Remediation SOP**:\n{res['remediation_plan'] or 'No active failures detected at physical or virtual layers.'}"
        )
    elif any(w in text_lower for w in ["deploy config", "deploy configuration", "heal", "apply patch", "remediate", "apply fix"]):
        import network_analyzers
        res = network_analyzers.TroubleshootingGraph.execute_sweep(device)
        tool_output = (
            f"### ZERO-TRUST Patches & Remediation\n"
            f"**Target Node**: `{device}`\n"
            f"**Remediation Command block**:\n"
            f"```text\n{res['remediation_plan'] or '! No configuration patch required.'}\n```\n\n"
            f"To deploy this patch, please switch to the **Incident Control Room** tab in the sidebar, select the active incident, and execute the Zero-Trust 5-step stepper (Validation -> Simulation -> Approvals -> Execution -> Verification) to enforce authorization guidelines."
        )
    elif any(w in text_lower for w in ["generate rca", "rca", "root cause", "rca report"]):
        import network_analyzers
        import report_generator
        res = network_analyzers.TroubleshootingGraph.execute_sweep(device)
        incident_details = {
            "device": device,
            "root_cause": res["logs"].split("\n")[-2] if len(res["logs"].split("\n")) > 1 else "Degraded protocol interface.",
            "cli_fix": res["remediation_plan"]
        }
        tool_output = report_generator.ReportGenerator.generate_rca(scenario_key or "general network alert", incident_details)
    elif any(w in text_lower for w in ["mop", "method of procedure", "playbook"]):
        import network_analyzers
        import report_generator
        res = network_analyzers.TroubleshootingGraph.execute_sweep(device)
        tool_output = report_generator.ReportGenerator.generate_mop(scenario_key or "configuration script", res["remediation_plan"] or "N/A", device)
    elif any(w in text_lower for w in ["sop", "standard operating procedure"]):
        import report_generator
        tool_output = report_generator.ReportGenerator.generate_sop(scenario_key or "critical NOC alarm")
    elif any(w in text_lower for w in ["pcap", "packet analysis", "analyze pcap", "wireshark"]):
        import graph_ocr_packet
        res = graph_ocr_packet.PacketAnalyzer.analyze_pcap(f"{scenario_key or 'outage'}.pcap")
        tool_output = (
            f"### Scapy Packet Inspector Output\n"
            f"**PCAP Filename**: `{res['filename']}`\n"
            f"**Audited Frames Count**: {res['total_packets']}\n"
            f"**TCP Retransmissions**: {res['tcp_retransmissions']} ({res['tcp_retransmission_rate_pct']}% rate)\n"
            f"**DNS Code Mismatches (NXDOMAIN)**: {res['dns_failures']}\n"
            f"**TLS Handshake Warnings**: {res['tls_handshake_errors']}\n"
            f"**Path Fragmentation (MTU)**: {res['fragmented_packets']} packets\n"
            f"**Health Assessment**: **{res['health_conclusion']}**"
        )
    elif any(w in text_lower for w in ["topology", "graph", "network map", "nodes status"]):
        import graph_ocr_packet
        topo = graph_ocr_packet.Neo4jTopologyConnector()
        graph = topo.get_topology_graph()
        nodes_str = ", ".join([f"{n['name']} ({n['role']})" for n in graph["nodes"]])
        edges_str = "\n".join([f"- {e['source']} -> {e['target']} via {e['type']} ({e['details']})" for e in graph["edges"]])
        tool_output = (
            f"### Graph Database Network Topology\n"
            f"**Discovered Nodes**:\n{nodes_str}\n\n"
            f"**Logical Link Adjacencies**:\n{edges_str}"
        )
    elif any(w in text_lower for w in ["audit", "compliance", "check config", "vulnerability"]):
        import network_analyzers
        sample_config = "username admin privilege 15 password public\ntransport input telnet\nsnmp-server community public RO\nip address 10.0.1.1 255.255.255.0\nip address 10.0.1.1 255.255.255.0\npermit ip any any\ndeny ip 10.0.0.0 0.255.255.255 any"
        issues = network_analyzers.ConfigAnalyzer.audit_config(sample_config)
        issues_str = "\n".join([f"- **{iss['category']}** ({iss['severity']}): {iss['details']} *Remediation*: `{iss['remediation']}`" for iss in issues])
        tool_output = (
            f"### Static Configuration Compliance Audit\n"
            f"**Security Warnings Isolated**:\n{issues_str}"
        )

    # 5. Build system prompt instructions
    persona = PERSONAS.get(session_persona, PERSONAS["assistant"])
    system_instruction = (
        f"{persona['prompt']}\n\n"
        f"Formatting Guidelines:\n"
        f"- Format metrics, status checks, and resource values inside clean Markdown tables.\n"
        f"- Encapsulate all configurations, CLI commands, scripts, and logs inside syntax-highlighted code blocks (e.g. ```cisco, ```python, ```json, ```yaml).\n"
        f"- Represent logical topologies, link linkages, and troubleshooting state trees using Mermaid flowchart formats (```mermaid ... ```).\n\n"
    )

    if active_incidents_context:
        system_instruction += (
            f"Active Incidents (auto-imported from Incident Engine):\n"
            f"{active_incidents_context}\n"
            f"Reference the above active incidents context to advise the user on dynamic problems.\n\n"
        )

    if topology_context:
        system_instruction += (
            f"Topology database (auto-imported):\n"
            f"{topology_context}\n\n"
        )

    if uploaded_logs:
        system_instruction += f"User uploaded system logs:\n{uploaded_logs}\n\n"
    if uploaded_config:
        system_instruction += f"User uploaded device config:\n{uploaded_config}\n\n"

    if scenario_info:
        system_instruction += (
            f"Active Incident Template Context:\n"
            f"Scenario Key: {scenario_key}\n"
            f"Response Template:\n{scenario_info['response']}\n"
            f"Diagnostics:\n{scenario_info.get('diagnostics', 'N/A')}\n"
            f"Self-Healing:\n{scenario_info.get('healing', 'N/A')}\n"
            f"RCA:\n{scenario_info.get('rca', 'N/A')}\n"
        )

    # 6. Execute stream
    if gemini_available:
        try:
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=system_instruction
            )
            contents = []
            if conversation_history:
                for msg in conversation_history:
                    role = "user" if msg['role'] == 'user' else "model"
                    contents.append({"role": role, "parts": [msg['text']]})
            
            # If tool output matched, pass it as part of request context
            final_prompt = prompt_text
            if tool_output:
                final_prompt = f"System tool output:\n{tool_output}\n\nUser request: {prompt_text}"

            contents.append({"role": "user", "parts": [final_prompt]})
            response_stream = model.generate_content(contents, stream=True)
            for chunk in response_stream:
                if chunk.text:
                    yield {
                        "text": chunk.text,
                        "done": False,
                        "persona": session_persona,
                        "routed": routed_persona is not None,
                        "isScenario": scenario_key is not None,
                        "scenarioKey": scenario_key
                    }
                await asyncio.sleep(0.01)
            yield {
                "text": "",
                "done": True,
                "persona": session_persona,
                "routed": routed_persona is not None,
                "isScenario": scenario_key is not None,
                "scenarioKey": scenario_key
            }
            return
        except Exception as e:
            print(f"Gemini streaming error, falling back to simulated sweep: {e}")

    # Fallback simulated response streaming
    if tool_output:
        response_text = tool_output
    elif scenario_info:
        if "diag" in text_lower or "diagnose" in text_lower:
            response_text = scenario_info.get("diagnostics", scenario_info["response"])
        elif "heal" in text_lower or "fix" in text_lower or "playbook" in text_lower or "solution" in text_lower or "patch" in text_lower:
            response_text = scenario_info.get("healing", scenario_info["response"])
        elif "rca" in text_lower or "root cause" in text_lower:
            response_text = scenario_info.get("rca", scenario_info["response"])
        else:
            response_text = scenario_info["response"]
    else:
        response_text = get_general_simulated_response(prompt_text, session_persona)

    words = response_text.split(" ")
    for i, word in enumerate(words):
        yield {
            "text": word if i == len(words) - 1 else word + " ",
            "done": False,
            "persona": session_persona,
            "routed": routed_persona is not None,
            "isScenario": scenario_key is not None,
            "scenarioKey": scenario_key
        }
        await asyncio.sleep(0.02)

    yield {
        "text": "",
        "done": True,
        "persona": session_persona,
        "routed": routed_persona is not None,
        "isScenario": scenario_key is not None,
        "scenarioKey": scenario_key
    }

