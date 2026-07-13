"""
Enhanced Intent Router – Phase 3 Intelligence Enhancement
Replaces the shallow keyword-matching auto_route_intent() with multi-signal
semantic scoring that selects the best persona transparently. Adds two new
personas (db_specialist, devops_eng) and improves routing accuracy via
contextual signals (incident type, device role, conversation topic).
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("noc.intent_router")


# ---------------------------------------------------------------------------
# Extended keyword maps for all personas (including 2 new ones)
# ---------------------------------------------------------------------------

PERSONA_KEYWORDS: Dict[str, List[str]] = {
    "net_genius": [
        "vpn", "ipsec", "isakmp", "bgp", "ospf", "eigrp", "vlan", "spanning-tree",
        "stp", "vtp", "trunk", "switch", "router", "route", "routing", "ping",
        "traceroute", "tracert", "interface", "port", "nat", "pat", "mpls",
        "qos", "access-list", "acl", "firewall rule", "wireless", "ssid",
        "netflow", "packet", "mtu", "arp", "mac address", "link-state",
        "convergence", "adjacency", "prefix", "subnet", "mask", "gateway",
        "nexthop", "peering", "as-path", "community", "transit", "peering",
        "tunnel", "gre", "isis", "rip", "redistribution",
    ],
    "win_admin": [
        "active directory", "ad", "domain controller", "iis", "hyper-v",
        "windows server", "winrm", "powershell", "group policy", "gpo",
        "dhcp", "dns windows", "rdp", "remote desktop", "kerberos", "ldap",
        "ntlm", "exchange", "sharepoint", "wsus", "sccm", "bitlocker",
        "windows event", "registry", "task scheduler", "windows update",
    ],
    "lin_admin": [
        "linux", "nginx", "apache", "httpd", "docker", "kubernetes", "k8s",
        "ssh", "cpu", "load average", "systemd", "journalctl", "cron",
        "bash", "shell", "iptables", "selinux", "ansible", "puppet", "chef",
        "rpm", "apt", "yum", "dnf", "proc", "kernel", "ulimit", "swap",
        "nfs", "samba", "rsync", "lvm", "mount", "df", "du", "grep",
        "nginx worker", "container", "pod", "helm",
    ],
    "noc_eng": [
        "health check", "daily check", "noc", "zabbix", "prtg", "nagios",
        "solarwinds", "sla", "monitoring", "alert", "alarm", "threshold",
        "uptime", "availability", "snmp", "trap", "mib", "oid",
        "netops", "event correlation", "escalation", "ticket", "incident",
        "on-call", "heartbeat", "synthetic monitoring",
    ],
    "sec_analyst": [
        "security", "firewall log", "acl check", "threat", "vulnerability",
        "audit", "brute force", "attack", "intrusion", "ids", "ips",
        "siem", "soc", "malware", "exploit", "cve", "patch", "pentest",
        "compliance", "nist", "iso 27001", "pci", "hipaa", "gdpr",
        "zero day", "ransomware", "phishing", "ddos", "dos", "scan",
        "port scan", "credential", "privilege escalation", "lateral movement",
        "darkweb", "threat intel", "ioc", "mitre", "att&ck",
    ],
    "cloud_eng": [
        "aws", "azure", "gcp", "google cloud", "vpc", "vnet", "cloud",
        "security group", "iam", "s3", "ec2", "rds", "lambda", "terraform",
        "cloudformation", "eks", "aks", "gke", "fargate", "nat gateway",
        "load balancer", "alb", "nlb", "cdn", "cloudfront", "route53",
        "azure ad", "managed identity", "service principal", "blob",
        "cost optimization", "reserved instance", "spot instance",
    ],
    "doc_specialist": [
        "sop", "mop", "runbook", "rca", "incident report", "document",
        "change request", "change management", "procedure", "policy",
        "post-mortem", "post mortem", "lessons learned", "audit trail",
        "compliance report", "executive summary", "report", "template",
        "standard", "guideline", "playbook",
    ],
    "auto_eng": [
        "configure vlan", "ansible", "playbook", "self-healing", "deploy config",
        "automation", "script", "python script", "terraform", "saltstack",
        "puppet", "chef", "ci/cd", "pipeline", "jenkins", "gitlab ci",
        "netmiko", "napalm", "nornir", "paramiko", "expect", "tcl",
        "zero-touch", "provisioning", "orchestration",
    ],
    "db_specialist": [
        "database", "sql", "mysql", "postgresql", "oracle", "mssql",
        "mongo", "mongodb", "redis", "elasticsearch", "query", "index",
        "replication", "clustering", "backup restore", "transaction",
        "deadlock", "slow query", "explain plan", "schema", "migration",
        "db connection", "connection pool", "jdbc", "odbc", "orm",
        "cassandra", "couchdb", "influxdb", "time series db",
    ],
    "devops_eng": [
        "devops", "pipeline", "cicd", "ci cd", "jenkins", "github actions",
        "gitlab", "bitbucket", "sonarqube", "nexus", "artifactory",
        "docker build", "image", "registry", "helm chart", "argocd",
        "flux", "gitops", "deployment", "rollout", "canary", "blue green",
        "observability", "prometheus", "grafana", "elk", "loki", "jaeger",
        "opentelemetry", "tracing", "metrics", "alertmanager",
    ],
    "assistant": [
        "hello", "hi", "help", "what can you", "navigate", "explain",
        "what is", "how does", "general", "overview",
    ],
}

# Weighted bonus signals based on context
DEVICE_ROLE_HINTS: Dict[str, str] = {
    "firewall": "sec_analyst",
    "router": "net_genius",
    "switch": "net_genius",
    "server": "lin_admin",
    "windows": "win_admin",
    "database": "db_specialist",
    "cloud": "cloud_eng",
}


# ---------------------------------------------------------------------------
# Intent Router
# ---------------------------------------------------------------------------

class IntentRouter:
    """
    Multi-signal intent classifier that selects the best AI persona for a query.
    Scoring combines keyword frequency, context hints, and conversation history.
    """

    @staticmethod
    def route(
        prompt: str,
        conversation_history: Optional[List[Dict]] = None,
        active_incidents: Optional[List[Dict]] = None,
        user_role: Optional[str] = None,
    ) -> Tuple[str, int, str]:
        """
        Route the prompt to the best persona.

        Returns
        -------
        (persona_key, score, reason)
        """
        text = prompt.lower()
        scores: Dict[str, int] = {k: 0 for k in PERSONA_KEYWORDS}

        # --- Signal 1: Keyword frequency scoring ---
        for persona, keywords in PERSONA_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    # Longer, more specific keywords get more weight
                    scores[persona] += len(kw.split())

        # --- Signal 2: Conversation context bonus ---
        if conversation_history:
            recent_text = " ".join(
                m.get("text", "") for m in conversation_history[-6:]
            ).lower()
            for persona, keywords in PERSONA_KEYWORDS.items():
                for kw in keywords:
                    if kw in recent_text:
                        scores[persona] += 1  # lighter weight for history

        # --- Signal 3: Active incident type bonus ---
        if active_incidents:
            for inc in active_incidents[:3]:
                desc = (inc.get("description", "") + " " + inc.get("root_cause", "")).lower()
                for role_hint, persona in DEVICE_ROLE_HINTS.items():
                    if role_hint in desc:
                        scores[persona] += 3

        # --- Signal 4: User role hint ---
        if user_role:
            role_lower = user_role.lower()
            if "security" in role_lower:
                scores["sec_analyst"] += 2
            elif "network" in role_lower:
                scores["net_genius"] += 2
            elif "linux" in role_lower or "devops" in role_lower:
                scores["lin_admin"] += 1
                scores["devops_eng"] += 1

        # --- Select winner ---
        # Exclude 'assistant' from competition unless it's the only match
        non_assistant = {k: v for k, v in scores.items() if k != "assistant"}
        best = max(non_assistant, key=lambda k: non_assistant[k])

        if non_assistant[best] == 0:
            return "assistant", 0, "No specific intent detected; defaulting to assistant."

        reason = IntentRouter._build_reason(best, text)
        return best, non_assistant[best], reason

    @staticmethod
    def _build_reason(persona: str, text: str) -> str:
        """Build a human-readable explanation of why this persona was selected."""
        matched_kws = [kw for kw in PERSONA_KEYWORDS.get(persona, []) if kw in text]
        top_kws = matched_kws[:3]
        persona_names = {
            "net_genius": "Network Engineer",
            "win_admin": "Windows Administrator",
            "lin_admin": "Linux Administrator",
            "noc_eng": "NOC Engineer",
            "sec_analyst": "Security Analyst",
            "cloud_eng": "Cloud Engineer",
            "doc_specialist": "Documentation Specialist",
            "auto_eng": "Automation Engineer",
            "db_specialist": "Database Specialist",
            "devops_eng": "DevOps Engineer",
            "assistant": "Friendly Assistant",
        }
        name = persona_names.get(persona, persona)
        kw_str = ", ".join(f"'{k}'" for k in top_kws) if top_kws else "contextual signals"
        return f"Routed to {name} based on: {kw_str}"


# ---------------------------------------------------------------------------
# Backward-compatible wrapper (drop-in replacement for auto_route_intent)
# ---------------------------------------------------------------------------

def auto_route_intent_enhanced(
    prompt_text: str,
    conversation_history: Optional[List[Dict]] = None,
    active_incidents: Optional[List[Dict]] = None,
    user_role: Optional[str] = None,
) -> Optional[str]:
    """
    Drop-in replacement for the original auto_route_intent() function.
    Returns persona key string or None if confidence is too low.
    """
    persona, score, reason = IntentRouter.route(
        prompt=prompt_text,
        conversation_history=conversation_history,
        active_incidents=active_incidents,
        user_role=user_role,
    )
    logger.debug(f"Intent routing: {reason} (score={score})")
    if score == 0:
        return None
    return persona
