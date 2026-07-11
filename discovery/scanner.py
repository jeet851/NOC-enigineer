import random
from typing import List, Dict

class NetworkScanner:
    """
    Simulates subnet sweeps to discover active network devices.
    """
    @staticmethod
    def scan_subnet(subnet: str) -> List[Dict[str, str]]:
        # Mock discovery sweep
        discovered = []
        base_ip = "10.0.10."
        vendors = ["Cisco", "Juniper", "Arista", "Linux"]
        roles = ["Web Server", "Switch", "Router", "Firewall"]
        
        for i in range(1, random.randint(3, 7)):
            ip = f"{base_ip}{random.randint(20, 250)}"
            vendor = random.choice(vendors)
            role = random.choice(roles)
            name = f"discovered-{vendor.lower()}-{i}"
            discovered.append({
                "name": name,
                "ip": ip,
                "vendor": vendor,
                "platform": "IOS-XE" if vendor == "Cisco" else "Junos",
                "role": role,
                "status": "Healthy"
            })
        return discovered
