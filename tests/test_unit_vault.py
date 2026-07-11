import pytest
from sqlalchemy.orm import Session
from models.vault import VaultSecret
from models.device import Device
from services.vault import VaultService

def test_vault_encryption_decryption():
    secret_text = "HighlySecurePassword123!"
    encrypted = VaultService.encrypt_raw(secret_text)
    assert encrypted != secret_text
    
    decrypted = VaultService.decrypt_raw(encrypted)
    assert decrypted == secret_text

def test_credential_validation():
    # SSH Key Validation
    ok, errs = VaultService.validate_credential("SSH Key", "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----")
    assert ok is True
    assert len(errs) == 0
    
    ok, errs = VaultService.validate_credential("SSH Key", "invalidkeycontents")
    assert ok is False
    assert any("PEM block" in e for e in errs)
    
    # SNMP Validation
    ok, errs = VaultService.validate_credential("SNMP Community", "public")
    assert ok is True
    
    ok, errs = VaultService.validate_credential("SNMP Community", "pub lic")
    assert ok is False
    assert any("whitespace" in e for e in errs)
    
    ok, errs = VaultService.validate_credential("SNMP Community", "abc")
    assert ok is False
    assert any("at least 4 characters" in e for e in errs)
    
    # API Key Validation
    ok, errs = VaultService.validate_credential("API Key", "1234567890123456")
    assert ok is True
    
    ok, errs = VaultService.validate_credential("API Key", "short")
    assert ok is False
    assert any("at least 16 characters" in e for e in errs)
    
    # Password Validation
    ok, errs = VaultService.validate_credential("Password", "shortpwd")
    assert ok is True
    
    ok, errs = VaultService.validate_credential("Password", "short")
    assert ok is False
    assert any("at least 8 characters" in e for e in errs)

def test_vault_crud_lifecycle(db_session: Session):
    # Add a secret
    secret_name = "test-switch-cred"
    VaultService.add_secret(db_session, secret_name, "Password", "switchpass123")
    
    # Get a list of secrets
    secrets = VaultService.get_secrets(db_session)
    assert secret_name in secrets
    assert secrets[secret_name]["type"] == "Password"
    
    # Retrieve & Decrypt secret
    decrypted_value = VaultService.get_secret(db_session, secret_name)
    assert decrypted_value == "switchpass123"
    
    # Delete secret
    deleted = VaultService.delete_secret(db_session, secret_name)
    assert deleted is True
    assert VaultService.get_secret(db_session, secret_name) is None

def test_credential_connection_simulation(db_session: Session):
    # Seed a device
    device_name = "test-router"
    device = db_session.query(Device).filter(Device.name == device_name).first()
    if not device:
        device = Device(
            name=device_name,
            ip="192.168.1.1",
            vendor="Cisco",
            platform="IOS",
            status="Healthy",
            role="Router",
            site="TestSite"
        )
        db_session.add(device)
        db_session.commit()

    # Add credentials
    secret_pass = "ssh_pass_success"
    secret_fail = "ssh_pass_fail"
    VaultService.add_secret(db_session, "ssh-pass-ok", "SSH Key", secret_pass)
    VaultService.add_secret(db_session, "ssh-pass-fail", "SSH Key", secret_fail)
    
    # Test connection success
    success, msg, logs = VaultService.test_credential_connection(db_session, "ssh-pass-ok", device_name)
    assert success is True
    assert "completed successfully" in msg
    assert "Key accepted" in logs
    
    # Test connection failure (simulated by having 'fail' in password)
    success, msg, logs = VaultService.test_credential_connection(db_session, "ssh-pass-fail", device_name)
    assert success is False
    assert "authentication failed" in msg
    assert "rejected" in logs
