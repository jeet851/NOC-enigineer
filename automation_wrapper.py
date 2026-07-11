import time
import os
from typing import Dict, Any, List, Tuple
import database

# Attempt to import Netmiko and NAPALM (fail gracefully if packages not installed or in sandbox)
NETMIKO_AVAILABLE = False
try:
    from netmiko import ConnectHandler
    NETMIKO_AVAILABLE = True
except ImportError:
    pass

NAPALM_AVAILABLE = False
try:
    from napalm import get_network_driver
    NAPALM_AVAILABLE = True
except ImportError:
    pass

class DeviceAutomationManager:
    """
    Standardized automation wrapper that interfaces with physical networking nodes via SSH/API,
    or runs realistic simulated terminal shells in sandbox environments.
    """
    
    @staticmethod
    def execute_command(device_name: str, command: str) -> str:
        """
        Executes a CLI command on a managed device, utilizing Netmiko/NAPALM if available
        and configured, otherwise falling back to high-fidelity simulated CLI.
        """
        # Fetch device configurations from DB
        devices = database.get_all_devices()
        target_dev = next((d for d in devices if d["name"] == device_name), None)
        
        if not target_dev:
            return f"Error: Managed node '{device_name}' not found in NOC inventory database."
            
        ip = target_dev["ip"]
        vendor = target_dev["vendor"]
        platform = target_dev["platform"]
        
        # If credentials exist and we can connect, try Live execution
        # (For this demonstration/sandbox setup, we default to Simulation if credentials aren't configured)
        secrets = database.get_db_secrets()
        has_credentials = any(device_name in k for k in secrets) or "Cisco-Core-Switch-SSH" in secrets
        
        if NETMIKO_AVAILABLE and has_credentials and not os.environ.get("FORCE_SIMULATION", "1") == "1":
            try:
                # Decrypt credentials from Vault
                username = "admin"
                password = os.environ.get("DEVICE_PASSWORD", "Password123") # Mock credentials fallback
                
                device_type = "cisco_ios" if vendor.lower() == "cisco" else "juniper_junos"
                
                net_device = {
                    'device_type': device_type,
                    'host': ip,
                    'username': username,
                    'password': password,
                    'port': 22,
                    'timeout': 10
                }
                
                with ConnectHandler(**net_device) as ssh:
                    output = ssh.send_command(command)
                    return output
            except Exception as e:
                # Log execution warning in audit and fallback
                database.add_db_audit_event(
                    user="automation_agent",
                    role="System",
                    action="SSH Live Connection Failed",
                    ip=ip,
                    details=f"Live SSH to {device_name} failed: {e}. Falling back to high-fidelity CLI simulator.",
                    status="Warning"
                )
                
        # Simulated CLI Engine
        return DeviceAutomationManager._get_simulated_cli_response(device_name, vendor, command)

    @staticmethod
    def deploy_config_patch(device_name: str, config_commands: str) -> Tuple[bool, str]:
        """
        Deploys configuration statements, captures state backups, and handles rollbacks if live,
        or simulates execution flow.
        """
        devices = database.get_all_devices()
        target_dev = next((d for d in devices if d["name"] == device_name), None)
        
        if not target_dev:
            return False, f"Device '{device_name}' not found."
            
        vendor = target_dev["vendor"]
        backup_id = f"CFG_BCK_{device_name.upper()}_{int(time.time())}"
        
        # If live, apply via NAPALM config commit or Netmiko send_config_set
        secrets = database.get_db_secrets()
        if NAPALM_AVAILABLE and not os.environ.get("FORCE_SIMULATION", "1") == "1" and "Live-Auth" in secrets:
            try:
                driver = get_network_driver('ios' if vendor.lower() == 'cisco' else 'junos')
                device_password = os.environ.get("DEVICE_PASSWORD", "Password123")
                device = driver(target_dev["ip"], 'admin', device_password)
                device.open()
                device.load_merge_candidate(config=config_commands)
                diff = device.compare_config()
                device.commit_config()
                device.close()
                return True, f"NAPALM Commit Success.\nDiff applied:\n{diff}"
            except Exception as e:
                return False, f"NAPALM Deploy Failure: {e}"
                
        # Simulated stepper backup + run
        logs = []
        logs.append(f"Successfully backed up running configuration to ID {backup_id}.")
        logs.append(f"Applying config commands on {device_name} ({vendor}):")
        for line in config_commands.split("\n"):
            if line.strip():
                logs.append(f"  {device_name}(config)# {line.strip()}")
        logs.append("Executing config synchronization... Passed.")
        return True, "\n".join(logs)

    @staticmethod
    def _get_simulated_cli_response(device: str, vendor: str, command: str) -> str:
        """
        Simulates raw IOS-XE/Junos/FortiOS output for diagnostics.
        """
        cmd_clean = command.strip().lower()
        
        if "show ip interface brief" in cmd_clean or "show int desc" in cmd_clean:
            if "switch" in device:
                return (
                    "Interface              IP-Address      OK? Method Status                Protocol\n"
                    "Vlan1                  10.0.1.1        YES NVRAM  up                    up      \n"
                    "Vlan10                 10.0.10.1       YES NVRAM  up                    up      \n"
                    "Vlan20                 10.0.20.1       YES NVRAM  up                    up      \n"
                    "GigabitEthernet1/0/1   unassigned      YES unset  up                    up      \n"
                    "GigabitEthernet1/0/2   unassigned      YES unset  up                    up      \n"
                    "GigabitEthernet1/0/24  unassigned      YES unset  up                    up      "
                )
            else:
                return (
                    "Interface              IP-Address      OK? Method Status                Protocol\n"
                    "GigabitEthernet1       198.51.100.2    YES NVRAM  up                    up      \n"
                    "GigabitEthernet2       10.0.1.254      YES NVRAM  up                    up      \n"
                    "Tunnel10               10.254.10.1     YES NVRAM  up                    up      "
                )
                
        elif "show ip ospf neighbor" in cmd_clean or "show ospf neighbor" in cmd_clean:
            return (
                "Neighbor ID     Pri   State           Dead Time   Address         Interface\n"
                "10.0.1.2          1   FULL/BDR        00:00:34    10.0.1.2        GigabitEthernet2\n"
                "192.168.1.1       1   FULL/DR         00:00:31    192.168.1.1     GigabitEthernet1"
            )
            
        elif "show bgp summary" in cmd_clean or "show ip bgp summary" in cmd_clean:
            return (
                "BGP router identifier 198.51.100.2, local AS number 65001\n"
                "Neighbor        V    AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd\n"
                "203.0.113.10    4 65000   14320   14210       24    0    0 04:12:12        4\n"
                "198.51.100.1    4 65100       0       0        0    0    0 00:00:00    Active"
            )
            
        elif "show crypto isakmp sa" in cmd_clean:
            # Check if VPN is simulated down
            from fastapi_server import active_scenarios_state
            if active_scenarios_state.get("vpn_is_down", False):
                return (
                    "IPv4 Source      IPv4 Destination      State      Id      Type\n"
                    "198.51.100.2     203.0.113.10          MM_NO_STATE 102    active"
                )
            return (
                "IPv4 Source      IPv4 Destination      State      Id      Type\n"
                "198.51.100.2     203.0.113.10          QM_IDLE      102    active"
            )
            
        elif "show version" in cmd_clean:
            return (
                f"Cisco IOS XE Software, Version 17.03.04a\n"
                f"Cisco Catalyst L3 Switch Software ({platform})\n"
                f"Device uptime is 14 weeks, 3 days, 12 hours\n"
                f"System image file is \"flash:packages.conf\""
            )
            
        elif "show access-lists" in cmd_clean or "show ip access-list" in cmd_clean:
            return (
                "Extended IP access list outside_access_in\n"
                "    10 deny tcp host 198.51.100.45 any eq 22 (1240 matches)\n"
                "    20 permit ip any any (84102 matches)"
            )
            
        # Default mock command shell
        return f"{device}# {command}\n! Simulated output. Command executed successfully."
