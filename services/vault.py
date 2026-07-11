import os
import re
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from models.vault import VaultSecret

from models.device import Device
from typing import Dict, Optional, List, Tuple

VAULT_KEY_FILE = "vault.key"
if not os.path.exists(VAULT_KEY_FILE):
    key = Fernet.generate_key()
    with open(VAULT_KEY_FILE, "wb") as f:
        f.write(key)
else:
    with open(VAULT_KEY_FILE, "rb") as f:
        key = f.read()

cipher_suite = Fernet(key)

class VaultService:
    @staticmethod
    def encrypt_raw(value: str) -> str:
        return cipher_suite.encrypt(value.encode()).decode()

    @staticmethod
    def decrypt_raw(encrypted_value: str) -> str:
        return cipher_suite.decrypt(encrypted_value.encode()).decode()

    @staticmethod
    def validate_credential(secret_type: str, value: str) -> Tuple[bool, List[str]]:
        """
        Validates structure and complexity of credential values depending on type.
        """
        errors = []
        val_strip = value.strip()
        
        if not val_strip:
            return False, ["Credential value cannot be empty."]
            
        type_lower = secret_type.lower()
        
        if "ssh key" in type_lower:
            if not (val_strip.startswith("-----BEGIN") and val_strip.endswith("-----")):
                errors.append("SSH Key must be formatted as a valid PEM block starting with '-----BEGIN' and ending with '-----'.")
                
        elif "snmp" in type_lower:
            if re.search(r"\s", val_strip):
                errors.append("SNMP Community string cannot contain whitespace characters.")
            if len(val_strip) < 4:
                errors.append("SNMP Community string must be at least 4 characters long.")
                
        elif "api key" in type_lower:
            if len(val_strip) < 16:
                errors.append("API Keys should be at least 16 characters long for sufficient entropy.")
            if re.search(r"\s", val_strip):
                errors.append("API Keys cannot contain whitespace.")
                
        elif "password" in type_lower or "tacacs" in type_lower:
            if len(val_strip) < 8:
                errors.append("Password credentials must be at least 8 characters long.")
                
        return len(errors) == 0, errors

    @staticmethod
    def test_credential_connection(db: Session, secret_name: str, device_name: str) -> Tuple[bool, str, str]:
        """
        Simulates testing a vaulted credential against a target device.
        """
        # Resolve secret
        secret = db.query(VaultSecret).filter(VaultSecret.name == secret_name).first()
        if not secret:
            return False, "Credential not found in Vault.", ""
            
        # Resolve device
        device = db.query(Device).filter(Device.name == device_name).first()
        if not device:
            return False, f"Target device '{device_name}' not found in network inventory.", ""
            
        secret_value = VaultService.decrypt_raw(secret.encrypted_value)
        type_lower = secret.secret_type.lower()
        
        logs = []
        logs.append(f"[{datetime_now_str()}] [VAULT TESTER] Initiating connectivity probe to {device.name} ({device.ip})...")
        logs.append(f"[{datetime_now_str()}] [VAULT TESTER] Credential resolved: '{secret_name}' (Type: {secret.secret_type})")
        
        success = True
        message = "Credential test completed successfully."
        
        if "ssh key" in type_lower:
            logs.append(f"[{datetime_now_str()}] [SSH CLIENT] Establishing secure SSHv2 tunnel to port 22...")
            logs.append(f"[{datetime_now_str()}] [SSH CLIENT] Negotiating encryption ciphers (aes256-gcm, curve25519)...")
            logs.append(f"[{datetime_now_str()}] [SSH CLIENT] Offering key '{secret_name}' to remote auth daemon...")
            if "fail" in secret_value.lower() or device.status == "Critical":
                logs.append(f"[{datetime_now_str()}] [SSH CLIENT] Authentication rejected by peer key validation daemon.")
                success = False
                message = "SSH authentication failed: Private key rejected."
            else:
                logs.append(f"[{datetime_now_str()}] [SSH CLIENT] Key accepted. Session shell opened. Shell prompt gathered: '{device.name}#'")
                
        elif "snmp" in type_lower:
            logs.append(f"[{datetime_now_str()}] [SNMP CLIENT] Sending SNMP GET request for sysObjectID.0 to {device.ip}:161...")
            logs.append(f"[{datetime_now_str()}] [SNMP CLIENT] Community validation string provided.")
            if secret_value in ["public", "private"] and device.vendor == "Cisco":
                logs.append(f"[{datetime_now_str()}] [SNMP CLIENT] WARNING: Using guessable default SNMP community string.")
            if "fail" in secret_value.lower():
                logs.append(f"[{datetime_now_str()}] [SNMP CLIENT] Request timeout. No response gathered from SNMP community string.")
                success = False
                message = "SNMP query failed: Timeout / invalid community string."
            else:
                logs.append(f"[{datetime_now_str()}] [SNMP CLIENT] Received response. OID sysDescr: '{device.platform} software version 12.0'")
                
        elif "api key" in type_lower:
            logs.append(f"[{datetime_now_str()}] [HTTP CLIENT] Dispatching secure HTTPS GET request to api interface...")
            logs.append(f"[{datetime_now_str()}] [HTTP CLIENT] Attaching API Token header context.")
            if "fail" in secret_value.lower():
                logs.append(f"[{datetime_now_str()}] [HTTP CLIENT] Received HTTP Response: 403 Forbidden. Invalid API Token.")
                success = False
                message = "API key test failed: 403 Access Denied."
            else:
                logs.append(f"[{datetime_now_str()}] [HTTP CLIENT] Received HTTP Response: 200 OK. Schema matches node profile.")
                
        else: # general password or TACACS check
            logs.append(f"[{datetime_now_str()}] [AUTH PROBE] Sending PAP authentication challenge via TACACS+ protocol...")
            if "fail" in secret_value.lower():
                logs.append(f"[{datetime_now_str()}] [AUTH PROBE] Access-Reject received from TACACS server.")
                success = False
                message = "Password/TACACS challenge failed: Access-Reject."
            else:
                logs.append(f"[{datetime_now_str()}] [AUTH PROBE] Access-Accept received. Session authenticated.")

        logs.append(f"[{datetime_now_str()}] [VAULT TESTER] Connection test result: {'PASSED' if success else 'FAILED'}")
        
        return success, message, "\n".join(logs)

    @staticmethod
    def get_secrets(db: Session) -> Dict[str, dict]:
        secrets = db.query(VaultSecret).all()
        
        if not secrets:
            # Seed default credentials
            now = datetime.utcnow()
            defaults = {
                "Cisco-Core-Switch-SSH": {"type": "SSH Key", "value": VaultService.encrypt_raw("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0G...mockkey...\n-----END RSA PRIVATE KEY-----"), "expires_days": 90},
                "Palo-Alto-Firewall-API": {"type": "API Key", "value": VaultService.encrypt_raw("paloalto_api_token_secure_99_alphanum"), "expires_days": 90},
                "SNMPv3-Community-String": {"type": "SNMP Community", "value": VaultService.encrypt_raw("snmpv3_auth_sha_aes256_public"), "expires_days": 90},
                "TACACS-Primary-Pass": {"type": "TACACS Credential", "value": VaultService.encrypt_raw("tacacs_primary_secure_pass_2026"), "expires_days": 90},
                "Expired-Router-TACACS-Pass": {"type": "TACACS Credential", "value": VaultService.encrypt_raw("expired_tacacs_challenge_failed"), "expires_days": -5}
            }
            for name, val in defaults.items():
                secret = VaultSecret(
                    name=name, 
                    secret_type=val["type"], 
                    encrypted_value=val["value"],
                    created_at=now - timedelta(days=30),
                    last_rotated=now - timedelta(days=30),
                    expires_at=now + timedelta(days=val["expires_days"]),
                    access_count=0
                )
                db.add(secret)
            db.commit()
            secrets = db.query(VaultSecret).all()
            
        return {
            s.name: {
                "type": s.secret_type,
                "value": s.encrypted_value,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "last_rotated": s.last_rotated.isoformat() if s.last_rotated else None,
                "access_count": s.access_count or 0
            }
            for s in secrets
        }

    @staticmethod
    def get_secret(db: Session, name: str) -> Optional[str]:
        secret = db.query(VaultSecret).filter(VaultSecret.name == name).first()
        if secret:
            # Audit log access count increment
            secret.access_count = (secret.access_count or 0) + 1
            db.commit()
            return VaultService.decrypt_raw(secret.encrypted_value)
        return None

    @staticmethod
    def add_secret(db: Session, name: str, secret_type: str, value: str):
        encrypted = VaultService.encrypt_raw(value)
        secret = db.query(VaultSecret).filter(VaultSecret.name == name).first()
        now = datetime.utcnow()
        if secret:
            secret.secret_type = secret_type
            secret.encrypted_value = encrypted
            secret.last_rotated = now
            secret.expires_at = now + timedelta(days=90)
        else:
            secret = VaultSecret(
                name=name, 
                secret_type=secret_type, 
                encrypted_value=encrypted,
                created_at=now,
                last_rotated=now,
                expires_at=now + timedelta(days=90),
                access_count=0
            )
            db.add(secret)
        db.commit()

    @staticmethod
    def delete_secret(db: Session, name: str) -> bool:
        secret = db.query(VaultSecret).filter(VaultSecret.name == name).first()
        if secret:
            db.delete(secret)
            db.commit()
            return True
        return False

def datetime_now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

