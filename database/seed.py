import os
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.session import SessionLocal, engine
from database.base import Base
from models.user import User
from models.device import Device
from models.alarm import Alarm
from models.vault import VaultSecret
from models.role import Role
from models.permission import Permission
from models.interface import Interface
from models.config_backup import ConfigurationBackup
from models.event import Event
from services.auth import get_password_hash
from datetime import datetime

def seed_db():
    print("Ensuring database tables are initialized...")
    
    # We let Alembic handle the schema updates, but create tables if they are missing
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 1. Seed Roles and Permissions
        role_count = db.scalar(select(sa_func_count(Role.id))) if 'sa_func_count' in globals() else db.query(Role).count()
        if role_count == 0:
            print("Seeding default Roles and Permissions...")
            
            # Create permissions
            p_read = Permission(name="read:all", description="Read-only access to all network data")
            p_write = Permission(name="write:configs", description="Propose and validate configuration changes")
            p_deploy = Permission(name="deploy:configs", description="Deploy patches and playbooks to live devices")
            p_admin = Permission(name="admin:all", description="Full administrative privileges")
            
            db.add_all([p_read, p_write, p_deploy, p_admin])
            db.flush()  # populate IDs
            
            # Create roles
            r_admin = Role(name="Admin", description="System Administrator with full access")
            r_admin.permissions = [p_read, p_write, p_deploy, p_admin]
            
            r_manager = Role(name="Manager", description="Operations Manager with configuration execution capabilities")
            r_manager.permissions = [p_read, p_write, p_deploy]
            
            r_engineer = Role(name="Network Engineer", description="Network Automation Analyst with write access (requires deployment approval)")
            r_engineer.permissions = [p_read, p_write]
            
            r_guest = Role(name="Guest", description="Auditor with read-only access")
            r_guest.permissions = [p_read]
            
            db.add_all([r_admin, r_manager, r_engineer, r_guest])
            db.commit()
            print("Roles and Permissions seeded successfully.")

        # Resolve seeded roles
        role_map = {r.name: r for r in db.scalars(select(Role)).all()}
        
        # 2. Seed Users
        user_count = db.query(User).count()
        if user_count == 0:
            print("Seeding default user profiles with secure bcrypt hashes & TOTP secrets...")
            default_users = [
                User(
                    username="admin", 
                    password_hash=get_password_hash("admin123"), 
                    role="Admin", 
                    name="System Administrator",
                    totp_secret="ADMINMFASECRET23",
                    mfa_enabled=True,
                    role_id=role_map["Admin"].id
                ),
                User(
                    username="operator", 
                    password_hash=get_password_hash("operator123"), 
                    role="Operator", 
                    name="Operations Manager",
                    totp_secret="OPERATORMFASECR",
                    mfa_enabled=True,
                    role_id=role_map["Manager"].id
                ),
                User(
                    username="engineer", 
                    password_hash=get_password_hash("engineer123"), 
                    role="Engineer", 
                    name="Network Automation Analyst",
                    totp_secret="ENGINEERMFASECR",
                    mfa_enabled=True,
                    role_id=role_map["Network Engineer"].id
                ),
                User(
                    username="read_only", 
                    password_hash=get_password_hash("readonly123"), 
                    role="Read Only", 
                    name="Auditor / Guest",
                    totp_secret="READONLYMFASECR",
                    mfa_enabled=True,
                    role_id=role_map["Guest"].id
                )
            ]
            db.add_all(default_users)
            db.commit()

        # 3. Seed Network Devices
        if db.query(Device).count() == 0:
            print("Seeding default network devices...")
            default_devices = [
                Device(name="router-hq", ip="198.51.100.2", vendor="Cisco", platform="IOS-XE", status="Healthy", role="HQ Edge Router / VPN Gateway", site="HQ", description="HQ Core Edge Gateway Router"),
                Device(name="asa-edge-01", ip="203.0.113.12", vendor="Cisco", platform="ASA OS", status="Healthy", role="Perimeter Protection Firewall", site="HQ", description="Primary Firewall Core Layer"),
                Device(name="sw-core-01", ip="10.0.1.1", vendor="Cisco", platform="Catalyst", status="Healthy", role="Core Layer-3 Routing Switch", site="HQ", description="Core Switch Segment A"),
                Device(name="sw-core-02", ip="10.0.1.2", vendor="Cisco", platform="Catalyst", status="Healthy", role="Core Layer-3 Routing Switch", site="HQ", description="Core Switch Segment B"),
                Device(name="db-srv-01", ip="10.0.20.10", vendor="Linux", platform="Ubuntu Server", status="Warning", role="Database Server", site="HQ", description="Database Host partition cluster"),
                Device(name="app-srv-01", ip="10.0.10.5", vendor="Linux", platform="Ubuntu Server", status="Healthy", role="DMZ Web Application Host", site="HQ", description="Web Server Node 01"),
                Device(name="app-srv-02", ip="10.0.10.6", vendor="Linux", platform="Ubuntu Server", status="Healthy", role="DMZ Web Application Host", site="HQ", description="Web Server Node 02"),
                Device(name="lb-01", ip="10.0.10.1", vendor="Linux", platform="Ubuntu Server", status="Healthy", role="Load Balancer", site="HQ", description="F5/HAProxy Load Balancer Node"),
                Device(name="mumbai-gw", ip="198.51.100.1", vendor="Cisco", platform="ISR 4331", status="Healthy", role="Branch Gateway Router", site="Mumbai", description="Mumbai Branch Edge Router"),
                Device(name="mumbai-core", ip="10.1.1.1", vendor="Cisco", platform="Catalyst 9300", status="Healthy", role="Branch Core Switch", site="Mumbai", description="Mumbai Switch Core"),
                Device(name="mumbai-fw", ip="10.1.1.254", vendor="Fortinet", platform="FortiGate", status="Healthy", role="Branch Firewall", site="Mumbai", description="Mumbai Firewall perimeter"),
                Device(name="mumbai-internet", ip="203.0.113.1", vendor="ISP", platform="Fiber", status="Healthy", role="ISP Gateway Interface", site="Mumbai", description="Mumbai Branch ISP link"),
                Device(name="mumbai-erp", ip="10.1.20.10", vendor="Linux", platform="RHEL 9", status="Healthy", role="ERP Application Host", site="Mumbai", description="Mumbai Branch ERP Server Node")
            ]
            db.add_all(default_devices)
            db.commit()

        # 4. Seed Interfaces
        if db.query(Interface).count() == 0:
            print("Seeding device interface configurations...")
            interfaces = [
                Interface(device_name="router-hq", name="GigabitEthernet1", ip_address="198.51.100.2", mac_address="52:54:00:12:34:56", status="up", speed="1Gbps", description="WAN edge uplink"),
                Interface(device_name="router-hq", name="GigabitEthernet2", ip_address="10.0.1.254", mac_address="52:54:00:12:34:57", status="up", speed="1Gbps", description="Core switch gateway link"),
                Interface(device_name="asa-edge-01", name="GigabitEthernet0/0", ip_address="203.0.113.12", mac_address="52:54:00:ab:cd:01", status="up", speed="1Gbps", description="outside firewall zone link"),
                Interface(device_name="asa-edge-01", name="GigabitEthernet0/1", ip_address="10.0.1.1", mac_address="52:54:00:ab:cd:02", status="up", speed="1Gbps", description="inside firewall zone link"),
                Interface(device_name="sw-core-01", name="Vlan10", ip_address="10.0.10.254", mac_address="52:54:00:22:22:10", status="up", speed="10Gbps", description="SVI Servers segment"),
                Interface(device_name="sw-core-01", name="Vlan20", ip_address="10.0.20.254", mac_address="52:54:00:22:22:20", status="up", speed="10Gbps", description="SVI Database segment")
            ]
            db.add_all(interfaces)
            db.commit()

        # 5. Seed Alarms
        if db.query(Alarm).count() == 0:
            print("Seeding default alarms...")
            default_alarms = [
                Alarm(id="AL-8891", timestamp=datetime.utcnow(), source="db-srv-01", metric="Disk Space (/var/log)", value="94%", severity="Warning", time_display="2h ago", status="Active"),
                Alarm(id="AL-8894", timestamp=datetime.utcnow(), source="asa-edge-01", metric="SSH Spray Attack", value="120 attempts/min", severity="Critical", time_display="5m ago", status="Active")
            ]
            db.add_all(default_alarms)
            db.commit()

        # 6. Seed Configuration Backups from memory baseline configuration
        if db.query(ConfigurationBackup).count() == 0:
            print("Seeding baseline configuration backups...")
            from services.config_manager import BASELINE_CONFIGS
            for dev_name, config_text in BASELINE_CONFIGS.items():
                bck_id = f"CFG_BCK_{dev_name.upper()}_1688537000"
                backup = ConfigurationBackup(
                    id=bck_id,
                    device_name=dev_name,
                    timestamp=datetime.utcnow(),
                    running_config=config_text,
                    startup_config=config_text,
                    version=1,
                    description="System initial provisioning baseline backup",
                    created_by="system"
                )
                db.add(backup)
            db.commit()

        # 7. Seed placeholder NOC Events
        if db.query(Event).count() == 0:
            print("Seeding initial network events...")
            events = [
                Event(source="router-hq", event_type="OSPF", severity="Info", message="OSPF Adjacency state change: neighbor 198.51.100.1 on GigabitEthernet1 from LOADING to FULL"),
                Event(source="asa-edge-01", event_type="Auth", severity="Warning", message="User 'guest' login failure on interface outside. Reason: Bad credentials"),
                Event(source="db-srv-01", event_type="System", severity="Warning", message="Disk utilization on logical partition /var/log crossed threshold 90%")
            ]
            db.add_all(events)
            db.commit()

        print("Database seeding completed successfully.")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
