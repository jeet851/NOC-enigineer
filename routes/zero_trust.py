import os
import socket
import ssl
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from models.vault import VaultSecret
from models.user import User
from services.vault import VaultService
from services.audit import AuditService
from services.alarm import AlarmService

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

router = APIRouter(prefix="/api/zero-trust", tags=["zero-trust-suite"])

# Request/Response schemas
class ValidateCertRequest(BaseModel):
    type: str  # "domain" or "pem"
    value: str

class RotateSSHRequest(BaseModel):
    name: str

class UpdateUserRoleRequest(BaseModel):
    username: str
    role: str

def analyze_x509_certificate(cert: x509.Certificate) -> dict:
    errors = []
    warnings = []
    
    # Expiry validation
    now = datetime.utcnow()
    try:
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc
    except AttributeError:
        # Fallback for older cryptography versions
        not_before = cert.not_valid_before
        not_after = cert.not_valid_after
        
    # Convert timezone-aware to naive for compatibility
    if not_before.tzinfo is not None:
        not_before = not_before.replace(tzinfo=None)
    if not_after.tzinfo is not None:
        not_after = not_after.replace(tzinfo=None)
    
    if now < not_before:
        errors.append(f"Certificate is not valid yet (starts {not_before.isoformat()}).")
    if now > not_after:
        errors.append(f"Certificate expired on {not_after.isoformat()}.")
        
    # Signature algorithm validation
    sig_alg = cert.signature_algorithm_oid._name
    if sig_alg in ["sha1WithRSAEncryption", "md5WithRSAEncryption"]:
        errors.append(f"Insecure signature algorithm used: {sig_alg}.")
        
    # Public key bits check
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
    
    pub_key = cert.public_key()
    key_size = getattr(pub_key, "key_size", None)
    if isinstance(pub_key, RSAPublicKey):
        if key_size and key_size < 2048:
            errors.append(f"Weak RSA public key size: {key_size} bits. Minimum 2048 bits required.")
    elif isinstance(pub_key, EllipticCurvePublicKey):
        if key_size and key_size < 256:
            errors.append(f"Weak Elliptic Curve key size: {key_size} bits. Minimum 256 bits required.")
        
    # Issuer check
    issuer = cert.issuer.rfc4514_string()
    subject = cert.subject.rfc4514_string()
    is_self_signed = issuer == subject
    if is_self_signed:
        warnings.append("Certificate is self-signed (Issuer matches Subject).")
        
    details = {
        "subject": subject,
        "issuer": issuer,
        "not_before": not_before.isoformat(),
        "not_after": not_after.isoformat(),
        "signature_algorithm": sig_alg or "Unknown",
        "key_size": key_size or 0,
        "is_self_signed": is_self_signed,
        "serial_number": str(cert.serial_number)
    }
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "details": details
    }

def validate_domain_certificate(domain: str, port: int = 443) -> dict:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # retrieve cert anyway so we can inspect it
    
    try:
        # Resolve clean domain name
        domain = domain.strip().replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
        conn = socket.create_connection((domain, port), timeout=5)
        with context.wrap_socket(conn, server_hostname=domain) as sock:
            der_cert = sock.getpeercert(binary_form=True)
            cert = x509.load_der_x509_certificate(der_cert, default_backend())
            return analyze_x509_certificate(cert)
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Failed to fetch certificate: {str(e)}"],
            "warnings": [],
            "details": {}
        }

def validate_pem_certificate(pem_str: str) -> dict:
    try:
        cert = x509.load_pem_x509_certificate(pem_str.strip().encode(), default_backend())
        return analyze_x509_certificate(cert)
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Invalid PEM certificate block: {str(e)}"],
            "warnings": [],
            "details": {}
        }

@router.get("/status")
async def get_zero_trust_status(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify auth
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(status_code=403, detail="Permission Denied.")
        
    now = datetime.utcnow()
    
    # Get database user to retrieve TOTP secret
    db_user = db.query(User).filter(User.username == user["username"]).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    from services.auth import get_totp_token, generate_totp_secret
    if not db_user.totp_secret:
        db_user.totp_secret = generate_totp_secret()
        db.commit()
        
    import time
    totp_token = get_totp_token(db_user.totp_secret)
    seconds_remaining = 30 - (int(time.time()) % 30)
    
    # 1. Audit Vault secrets for expiration
    secrets = db.query(VaultSecret).all()
    expired_count = 0
    for s in secrets:
        if s.expires_at and s.expires_at < now:
            expired_count += 1
            # Trigger Alarm for expired credential
            AlarmService.add_alarm(
                db=db,
                alarm_id=f"SEC-EXP-{s.name.replace(' ', '-')}",
                source="Vault Store",
                metric="Expired Credential Alert",
                value=f"Expired on {s.expires_at.strftime('%Y-%m-%d')}",
                severity="Critical",
                time_display="Just now"
            )
            
    # 2. Check local HTTPS SSL cert status
    local_cert_status = {"valid": True, "errors": [], "warnings": [], "details": {}}
    if os.path.exists("localhost.crt"):
        try:
            with open("localhost.crt", "r") as f:
                pem_data = f.read()
            local_cert_status = validate_pem_certificate(pem_data)
            if not local_cert_status["valid"]:
                AlarmService.add_alarm(
                    db=db,
                    alarm_id="SEC-CERT-LOCAL-ERR",
                    source="HTTPS Daemon",
                    metric="SSL Certificate Invalid",
                    value="Failed validations",
                    severity="Warning",
                    time_display="Just now"
                )
        except Exception as e:
            local_cert_status = {"valid": False, "errors": [str(e)], "warnings": [], "details": {}}
    else:
        local_cert_status = {"valid": False, "errors": ["localhost.crt not found on server disk."], "warnings": [], "details": {}}
        
    return {
        "mfaStatus": "Strict",
        "rbacStatus": "Strict",
        "apiAuthStatus": "Enforced",
        "expiredSecretsCount": expired_count,
        "localCert": local_cert_status,
        "totp": totp_token,
        "secondsRemaining": seconds_remaining,
        "secret": db_user.totp_secret,
        "username": db_user.username
    }


@router.post("/rotate-ssh")
async def rotate_ssh_key(req: RotateSSHRequest, request: Request, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Restrict key rotation to Admin and Operator roles
    if user["role"] not in ["Admin", "Operator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Only Admin and Operator roles can rotate credentials."
        )
        
    name = req.name.strip()
    secret = db.query(VaultSecret).filter(VaultSecret.name == name).first()
    if not secret:
        raise HTTPException(status_code=404, detail="Secret credential not found.")
        
    if "ssh key" not in secret.secret_type.lower():
        raise HTTPException(
            status_code=400,
            detail=f"Rotation failed: Secret '{name}' is of type '{secret.secret_type}' (Must be SSH Key)."
        )
        
    # Generate a brand-new cryptographically secure RSA key pair
    try:
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        pem_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        ssh_public = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        ).decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Key generation failed: {str(e)}")
        
    # Save encrypted private key back to vault
    secret.encrypted_value = VaultService.encrypt_raw(pem_private)
    secret.last_rotated = datetime.utcnow()
    secret.expires_at = datetime.utcnow() + timedelta(days=90) # extends expiry by 90 days
    db.commit()
    
    # Auto-resolve expired alarms for this secret
    AlarmService.resolve_alarm(db, f"SEC-EXP-{secret.name.replace(' ', '-')}")
    
    # Audit log rotation
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Rotate SSH Key",
        ip=request.client.host if request.client else "0.0.0.0",
        details=f"Successfully generated and rotated key pair for '{name}'."
    )
    
    return {
        "status": "success",
        "name": name,
        "privateKey": pem_private,
        "publicKey": ssh_public,
        "message": f"Successfully rotated key pair for credential '{name}'."
    }

@router.post("/validate-certificate")
async def api_validate_certificate(req: ValidateCertRequest, user: dict = Depends(get_current_user)):
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(status_code=403, detail="Permission Denied.")
        
    val_type = req.type.strip().lower()
    value = req.value.strip()
    
    if val_type == "domain":
        return validate_domain_certificate(value)
    elif val_type == "pem":
        return validate_pem_certificate(value)
    else:
        raise HTTPException(status_code=400, detail="Invalid certificate validation type. Must be 'domain' or 'pem'.")

@router.post("/update-role")
async def update_user_role(req: UpdateUserRoleRequest, request: Request, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Role modification restricted strictly to Admin
    if user["role"] not in ["Admin"]:
        raise HTTPException(
            status_code=403,
            detail="Permission Denied: Dynamic role configuration is restricted to Admin role."
        )
        
    target_username = req.username.strip().lower()
    new_role = req.role.strip()
    
    if new_role not in ["Admin", "Operator", "Engineer", "Read Only"]:
        raise HTTPException(status_code=400, detail="Invalid role name specified.")
        
    target_user = db.query(User).filter(User.username == target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
        
    old_role = target_user.role
    target_user.role = new_role
    db.commit()
    
    # Audit log dynamic role shift
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Modify User Role",
        ip=request.client.host if request.client else "0.0.0.0",
        details=f"Changed role of user '{target_username}' from '{old_role}' to '{new_role}'"
    )
    
    return {
        "status": "success",
        "username": target_username,
        "oldRole": old_role,
        "newRole": new_role
    }
