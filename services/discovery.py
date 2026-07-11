import asyncio
import random
import os
from datetime import datetime
from sqlalchemy.orm import Session

from models.device import Device
from models.discovery import DiscoveryLog
from topology.manager import TopologyManager
from websocket.server import sio

# Initialize topology manager
topology_manager = TopologyManager()

class DiscoveryService:
    @staticmethod
    async def run_subnet_discovery(subnet: str, db: Session) -> int:
        """
        Runs a simulated discovery scan sweep on the target subnet,
        extracts parameters, updates inventory + topology, and emits Socket.IO messages.
        """
        # Create unique log file or string logs
        logs = []
        def log_event(msg: str):
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            logs.append(f"[{timestamp}] {msg}")
            print(f"[DISCOVERY] {msg}")

        log_event(f"Starting discovery sweep on subnet: {subnet}")
        await sio.emit("discovery_status", {"status": "started", "subnet": subnet})
        await asyncio.sleep(1) # simulate sweep latency

        # Map of simulated nodes to discover based on vendor/platform request
        devices_to_discover = [
            {
                "hostname": "cisco-core-switch",
                "ip": "10.0.10.5",
                "vendor": "Cisco",
                "platform": "IOS-XE 17.3.1",
                "role": "Switch",
                "model": "Catalyst 9300L",
                "serial": "SN-CISCO-88912",
                "interfaces": ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2", "GigabitEthernet1/0/3"],
                "neighbors": [{"local": "GigabitEthernet1/0/1", "remote_host": "juniper-srx-edge", "remote_port": "ge-0/0/0"}],
                "vlans": [1, 10, 20, 99],
                "vrfs": ["default", "mgmt"],
                "routing": ["OSPF", "BGP"]
            },
            {
                "hostname": "juniper-srx-edge",
                "ip": "10.0.10.6",
                "vendor": "Juniper",
                "platform": "Junos 21.2R1.10",
                "role": "Firewall",
                "model": "SRX300-Edge",
                "serial": "SN-JUNIPER-77123",
                "interfaces": ["ge-0/0/0", "ge-0/0/1", "ge-0/0/2"],
                "neighbors": [{"local": "ge-0/0/1", "remote_host": "arista-leaf-01", "remote_port": "Ethernet1"}],
                "vlans": [1, 10, 50],
                "vrfs": ["default", "VRF-External"],
                "routing": ["BGP", "Static"]
            },
            {
                "hostname": "arista-leaf-01",
                "ip": "10.0.10.12",
                "vendor": "Arista",
                "platform": "EOS 4.26.1F",
                "role": "Switch",
                "model": "DCS-7050SX3",
                "serial": "SN-ARISTA-33215",
                "interfaces": ["Ethernet1", "Ethernet2", "Ethernet3"],
                "neighbors": [{"local": "Ethernet2", "remote_host": "fortinet-utm-fw", "remote_port": "port1"}],
                "vlans": [1, 10, 20, 30],
                "vrfs": ["default", "VRF-Production"],
                "routing": ["OSPF"]
            },
            {
                "hostname": "fortinet-utm-fw",
                "ip": "10.0.10.20",
                "vendor": "Fortinet",
                "platform": "FortiOS 7.0.5",
                "role": "Firewall",
                "model": "FortiGate 100F",
                "serial": "SN-FORTI-44912",
                "interfaces": ["port1", "port2", "wan1"],
                "neighbors": [{"local": "port2", "remote_host": "paloalto-edge-fw", "remote_port": "ethernet1/1"}],
                "vlans": [1, 99],
                "vrfs": ["default"],
                "routing": ["Static"]
            },
            {
                "hostname": "paloalto-edge-fw",
                "ip": "10.0.10.22",
                "vendor": "Palo Alto",
                "platform": "PAN-OS 10.1.3",
                "role": "Firewall",
                "model": "PA-820",
                "serial": "SN-PALO-55123",
                "interfaces": ["ethernet1/1", "ethernet1/2"],
                "neighbors": [],
                "vlans": [1],
                "vrfs": ["default", "VRF-Trust", "VRF-Untrust"],
                "routing": ["BGP"]
            },
            {
                "hostname": "huawei-ar-router",
                "ip": "10.0.10.30",
                "vendor": "Huawei",
                "platform": "VRP 8.1",
                "role": "Router",
                "model": "NetEngine AR6120",
                "serial": "SN-HUAWEI-66124",
                "interfaces": ["GigabitEthernet0/0/0", "GigabitEthernet0/0/1"],
                "neighbors": [{"local": "GigabitEthernet0/0/0", "remote_host": "cisco-core-switch", "remote_port": "GigabitEthernet1/0/2"}],
                "vlans": [1, 100],
                "vrfs": ["default"],
                "routing": ["OSPF", "IS-IS"]
            },
            {
                "hostname": "linux-db-srv",
                "ip": "10.0.10.40",
                "vendor": "Linux",
                "platform": "Ubuntu 22.04 LTS",
                "role": "Server",
                "model": "PowerEdge R740",
                "serial": "SN-LINUX-99124",
                "interfaces": ["eth0", "eth1"],
                "neighbors": [],
                "vlans": [],
                "vrfs": [],
                "routing": ["Static"]
            },
            {
                "hostname": "win-ad-domain",
                "ip": "10.0.10.42",
                "vendor": "Windows",
                "platform": "Windows Server 2022",
                "role": "Server",
                "model": "ProLiant DL360",
                "serial": "SN-WIN-33921",
                "interfaces": ["Ethernet0", "Ethernet1"],
                "neighbors": [],
                "vlans": [],
                "vrfs": [],
                "routing": ["Static"]
            },
            {
                "hostname": "vmware-esxi-host",
                "ip": "10.0.10.45",
                "vendor": "VMware",
                "platform": "ESXi 7.0u3",
                "role": "Server",
                "model": "vSphere ESXi",
                "serial": "SN-VMWARE-11223",
                "interfaces": ["vmnic0", "vmnic1", "vswitch0"],
                "neighbors": [],
                "vlans": [],
                "vrfs": [],
                "routing": ["Static"]
            }
        ]

        total = len(devices_to_discover)
        for idx, item in enumerate(devices_to_discover):
            hostname = item["hostname"]
            ip = item["ip"]
            vendor = item["vendor"]
            platform = item["platform"]
            model = item["model"]
            serial = item["serial"]
            role = item["role"]

            log_event(f"Probing target IP: {ip} via SNMP v3 / SSH credential sweep...")
            await asyncio.sleep(0.5) # simulate latency

            log_event(f"Device responded! Vendor detected: {vendor} ({platform})")
            log_event(f"Resolved Metadata -> Hostname: {hostname} | Model: {model} | Serial: {serial}")
            log_event(f"Discovered interfaces: {', '.join(item['interfaces'])}")
            if item["vlans"]:
                log_event(f"Discovered VLANs: {item['vlans']}")
            if item["vrfs"]:
                log_event(f"Discovered VRFs: {item['vrfs']}")
            if item["routing"]:
                log_event(f"Active routing protocols: {', '.join(item['routing'])}")

            # 1. Update/Add database network inventory table
            device = db.query(Device).filter(Device.name == hostname).first()
            if not device:
                device = Device(
                    name=hostname,
                    ip=ip,
                    vendor=vendor,
                    platform=platform,
                    status="Healthy",
                    role=role,
                    site="HQ-NOC",
                    description=f"Auto-discovered via subnet sweep of {subnet} on {datetime.utcnow().strftime('%Y-%m-%d')}"
                )
                db.add(device)
            else:
                device.ip = ip
                device.vendor = vendor
                device.platform = platform
                device.description = f"Updated via discovery of {subnet} on {datetime.utcnow().strftime('%Y-%m-%d')}"
            db.commit()

            # 2. Update topology automatically (Node creation)
            topology_manager.add_node(hostname, f"{vendor} {model}", ip, vendor)

            # 3. Add topology link edges for LLDP neighbors
            for neigh in item["neighbors"]:
                topology_manager.add_link(
                    source=hostname,
                    target=neigh["remote_host"],
                    link_type="LLDP",
                    details=f"{neigh['local']} -> {neigh['remote_port']}"
                )
                log_event(f"Discovered LLDP Neighbor link: {hostname} ({neigh['local']}) -> {neigh['remote_host']} ({neigh['remote_port']})")

            # 4. Broadcast live Socket.IO update
            percent = int(((idx + 1) / total) * 100)
            await sio.emit("discovery_device", {
                "hostname": hostname,
                "ip": ip,
                "vendor": vendor,
                "platform": platform,
                "model": model,
                "serial": serial,
                "status": "Healthy"
            })
            await sio.emit("discovery_progress", {
                "percent": percent,
                "message": f"Successfully mapped and indexed {hostname} ({vendor})"
            })
            
            await asyncio.sleep(0.3)

        log_event(f"Completed discovery sweep on subnet: {subnet}. Total devices found: {total}")
        await sio.emit("discovery_status", {"status": "completed", "subnet": subnet, "devices_found": total})

        # Save run logs to database
        db_log = DiscoveryLog(
            subnet=subnet,
            status="Completed",
            devices_found=total,
            log_output="\n".join(logs)
        )
        db.add(db_log)
        db.commit()

        return total
