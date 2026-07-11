import asyncio
import random
import logging
import os
import json
from datetime import datetime
from sqlalchemy.orm import Session

from database.session import SessionLocal
from services.device import DeviceService
from services.telemetry import TelemetryService
from services.alarm import AlarmService
from routes.config import active_scenarios_state  # Share scenario states dynamically
from websocket.server import sio

from api.config import settings

logger = logging.getLogger("noc.telemetry")

# Monitor interval driven by settings (configurable via TELEMETRY_INTERVAL_SECONDS env var)
monitor_interval_seconds = settings.TELEMETRY_INTERVAL_SECONDS
syslog_file_path = "syslogs.log"

def write_local_syslog(device_name: str, message: str):
    """
    Appends syslog entries to a local syslogs.log file.
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {device_name}: {message}\n"
    try:
        with open(syslog_file_path, "a") as f:
            f.write(entry)
    except Exception as e:
        logger.error(f"Error writing local syslog: {e}")

from services.redis_cache import RedisCacheManager

async def run_network_telemetry_loop():
    """
    Asynchronous background job that runs every 5 seconds to collect metrics,
    store them, broadcast them, and evaluate thresholds to trigger alarms.
    """
    logger.info(
        "Zero-Trust Monitoring Engine active",
        extra={"interval_seconds": monitor_interval_seconds}
    )
    
    # Store previous alarm states to prevent duplicate Socket.IO emits
    active_alarms_tracker = {}

    while True:
        db = SessionLocal()
        try:
            # Check if 10k devices simulation is active
            simulate_active = RedisCacheManager.get("simulate_10k_devices") == "true"
            
            devices = DeviceService.get_all_devices(db)
            devices_list = [d for d in devices]
            
            telemetry_mappings = []
            
            # Start timer to measure database insert latencies
            db_write_start = datetime.utcnow()
            
            for dev in devices_list:
                dev_name = dev.name
                
                # 1. Base Performance Metrics (Healthy default ranges)
                ping_rtt = round(random.uniform(1.2, 5.8), 2)
                packet_loss = 0.0
                jitter = round(random.uniform(0.1, 0.9), 2)
                bw_in = round(random.uniform(150.0, 450.0), 2) # Inbound Bandwidth Mbps
                bw_out = round(random.uniform(100.0, 300.0), 2) # Outbound Bandwidth Mbps
                
                # 2. Resource Metrics
                cpu = random.randint(12, 38)
                ram = random.randint(30, 52)
                temp = random.randint(38, 55) # Celsius
                
                # 3. Interfaces & Errors
                interfaces_up = 4
                interfaces_down = 0
                crc_errors = 0
                packet_drops = 0
                
                # 4. Protocols & Tunnel states
                bgp_peer_status = "Established"
                ospf_neighbor_count = 2
                vpn_tunnels_up = 2
                fw_sessions = random.randint(1500, 3500)
                
                status = "Healthy"
                syslog_message = None

                # Apply simulated scenario impacts
                if dev_name == "router-hq" and active_scenarios_state.get("vpn_is_down", False):
                    ping_rtt = 0.0
                    packet_loss = 100.0
                    jitter = 0.0
                    vpn_tunnels_up = 0
                    bgp_peer_status = "Down"
                    status = "Critical"
                    syslog_message = "VPN-3-TUNNEL_DOWN: IPSec tunnel to Remote-Office changed state to down. BGP session closed."
                
                elif dev_name == "app-srv-02" and active_scenarios_state.get("server_cpu_100", False):
                    cpu = 100
                    temp = 84
                    status = "Warning"
                    syslog_message = "SYS-1-CPU_OVERHEAT: Chassis temperature exceeded Warning limit: 84C. CPU at 100%."
                    
                elif dev_name == "db-srv-01" and active_scenarios_state.get("log_partition_94", False):
                    status = "Warning"
                    cpu = random.randint(45, 62)
                    ram = random.randint(88, 95)
                    syslog_message = "SYS-4-MEM_LOW: System memory partition threshold exceeded 90% (Active: 95%)."
                    
                elif dev_name == "asa-edge-01" and active_scenarios_state.get("ssh_spray_attack", False):
                    status = "Warning"
                    cpu = random.randint(85, 96)
                    fw_sessions = random.randint(12000, 15000)
                    packet_drops = random.randint(50, 150)
                    syslog_message = "SEC-3-FLOOD_ATTACK: SSH authentication flood detected. Active sessions: 14500. Drop count: 120."
                
                # Introduce occasional random telemetry spikes to keep the dashboard dynamic
                if status == "Healthy" and random.random() < 0.02:
                    ping_rtt = round(random.uniform(15.0, 45.0), 2)
                    jitter = round(random.uniform(4.0, 9.0), 2)
                    packet_loss = 2.0
                    crc_errors = random.randint(1, 5)
                    syslog_message = "PORT-4-CRC_ERRORS: CRC alignment errors detected on Gi1/0/1."
                
                # Generate default periodic syslogs if no scenario is active
                if not syslog_message and random.random() < 0.1:
                    syslog_message = f"SYS-6-INFO: Interface states are stable. gRPC streaming telemetry active (SNMP v3: Valid)."

                # Write syslogs to local file and broadcast
                if syslog_message:
                    write_local_syslog(dev_name, syslog_message)
                    await sio.emit("syslog_message", {
                        "timestamp": datetime.utcnow().isoformat(),
                        "device": dev_name,
                        "message": syslog_message
                    })

                # 5. Evaluate Threshold Alerts (Raise/Resolve Alarms)
                async def check_alarm(alarm_id: str, trigger_condition: bool, metric: str, val_str: str, severity: str):
                    tracker_key = f"{dev_name}:{alarm_id}"
                    if trigger_condition:
                        AlarmService.add_alarm(
                            db=db,
                            alarm_id=alarm_id,
                            source=dev_name,
                            metric=metric,
                            value=val_str,
                            severity=severity,
                            time_display="Just now"
                        )
                        from incident_engine.engine import IncidentEngine
                        await IncidentEngine.process_abnormality(
                            db=db,
                            device_name=dev_name,
                            metric=metric,
                            value=val_str,
                            severity=severity
                        )
                        if not active_alarms_tracker.get(tracker_key, False):
                            active_alarms_tracker[tracker_key] = True
                            await sio.emit("alarm_update", {
                                "id": alarm_id,
                                "source": dev_name,
                                "metric": metric,
                                "value": val_str,
                                "severity": severity,
                                "status": "Active"
                            })
                    else:
                        if active_alarms_tracker.get(tracker_key, False) or AlarmService.resolve_alarm(db, alarm_id):
                            active_alarms_tracker[tracker_key] = False
                            from incident_engine.engine import IncidentEngine
                            await IncidentEngine.process_resolution(
                                db=db,
                                device_name=dev_name,
                                metric=metric
                            )
                            await sio.emit("alarm_update", {
                                "id": alarm_id,
                                "source": dev_name,
                                "status": "Resolved"
                            })

                await check_alarm(f"AL-CPU-{dev_name}", cpu >= 90, "CPU Utilization", f"{cpu}%", "Critical")
                await check_alarm(f"AL-LOSS-{dev_name}", packet_loss > 5.0, "Packet Loss", f"{packet_loss}%", "Critical")
                await check_alarm(f"AL-TEMP-{dev_name}", temp > 80, "Chassis Temperature", f"{temp}C", "Warning")
                await check_alarm(f"AL-VPN-{dev_name}", vpn_tunnels_up == 0 and dev_name == "router-hq", "VPN Status", "Offline", "Critical")
                await check_alarm(f"AL-ROUTE-{dev_name}", bgp_peer_status == "Down", "Routing Protocols", "BGP Peer Offline", "Critical")

                if cpu >= 90 or packet_loss > 5.0 or bgp_peer_status == "Down":
                    status = "Critical"
                elif temp > 80 or ram >= 85:
                    status = "Warning"

                # Cache status and telemetry payload in Redis for 100x faster API reads
                telemetry_payload = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "device": dev_name,
                    "sensor_path": "openconfig-interfaces:interfaces/interface/state",
                    "data": {
                        "cpu": cpu,
                        "ram": ram,
                        "temperature": temp,
                        "ping_rtt": ping_rtt,
                        "packet_loss": packet_loss,
                        "jitter": jitter,
                        "bandwidth_in_mbps": bw_in,
                        "bandwidth_out_mbps": bw_out,
                        "interfaces": {
                            "up_count": interfaces_up,
                            "down_count": interfaces_down,
                            "crc_errors": crc_errors,
                            "drops": packet_drops
                        },
                        "routing": {
                            "bgp_peer": bgp_peer_status,
                            "ospf_neighbors": ospf_neighbor_count
                        },
                        "vpn_tunnels_up": vpn_tunnels_up,
                        "firewall_sessions": fw_sessions,
                        "snmp_status": "Authenticated (v3)",
                        "status": status
                    }
                }
                RedisCacheManager.set(f"device:status:{dev_name}", status)
                RedisCacheManager.set(f"telemetry:latest:{dev_name}", json.dumps(telemetry_payload))

                # Queue telemetry database insert for bulk flush
                telemetry_mappings.append({
                    "device_name": dev_name,
                    "ping_rtt": ping_rtt,
                    "min_rtt": max(0.1, ping_rtt - round(random.uniform(0.1, 0.5), 2)),
                    "max_rtt": ping_rtt + round(random.uniform(0.5, 2.5), 2),
                    "packet_loss": packet_loss,
                    "jitter": jitter,
                    "cpu": cpu,
                    "ram": ram,
                    "interface_errors": crc_errors + packet_drops,
                    "status": status,
                    "timestamp": datetime.utcnow()
                })
                
                # Update status in catalog
                DeviceService.update_device_status(db, dev_name, status)
                await sio.emit("telemetry_update", telemetry_payload)

            # Process 10,000 devices simulation in memory to prevent SQLite locking
            if simulate_active:
                # Cache stats for monitoring API
                RedisCacheManager.set("monitoring:event_rate", "20000") # 20k events/sec under 10k devices loop
                current_total = int(RedisCacheManager.get("monitoring:total_events") or 0)
                RedisCacheManager.set("monitoring:total_events", str(current_total + 10000))
                
                # Seed or update 10,000 devices in cache
                for i in range(1, 10001):
                    vdev_name = f"edge-sw-{i:04d}"
                    v_cpu = random.randint(10, 40)
                    v_ram = random.randint(25, 48)
                    v_temp = random.randint(35, 52)
                    v_status = "Healthy"
                    
                    v_payload = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "device": vdev_name,
                        "sensor_path": "openconfig-interfaces:interfaces/interface/state",
                        "data": {
                            "cpu": v_cpu,
                            "ram": v_ram,
                            "temperature": v_temp,
                            "ping_rtt": round(random.uniform(1.5, 3.5), 2),
                            "packet_loss": 0.0,
                            "jitter": 0.2,
                            "interfaces": {"up_count": 24, "down_count": 0, "crc_errors": 0, "drops": 0},
                            "routing": {"bgp_peer": "Established", "ospf_neighbors": 2},
                            "vpn_tunnels_up": 1,
                            "firewall_sessions": 450,
                            "snmp_status": "Authenticated (v3)",
                            "status": v_status
                        }
                    }
                    RedisCacheManager.set(f"device:status:{vdev_name}", v_status)
                    RedisCacheManager.set(f"telemetry:latest:{vdev_name}", json.dumps(v_payload))
            else:
                # Normal mode
                RedisCacheManager.set("monitoring:event_rate", str(len(devices_list) // 5))
                current_total = int(RedisCacheManager.get("monitoring:total_events") or 0)
                RedisCacheManager.set("monitoring:total_events", str(current_total + len(devices_list)))

            # Executing database bulk transaction (atomic write)
            if telemetry_mappings:
                from models.telemetry import TelemetryLog
                db.bulk_insert_mappings(TelemetryLog, telemetry_mappings)
                db.commit()
                
            db_write_end = datetime.utcnow()
            db_write_latency_ms = int((db_write_end - db_write_start).total_seconds() * 1000)
            RedisCacheManager.set("monitoring:db_latency_ms", str(db_write_latency_ms))

        except Exception as e:
            logger.error(f"Error in Telemetry monitor run: {e}", exc_info=True)
        finally:
            db.close()
            
        await asyncio.sleep(monitor_interval_seconds)
