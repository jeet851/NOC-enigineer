import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from api.deps import get_db, get_current_user
from schemas.vault import CredentialTestRequest, CredentialTestResponse, CredentialValidationResponse
from services.vault import VaultService
from services.audit import AuditService

router = APIRouter(prefix="/api/vault", tags=["credential-vault"])
logger = logging.getLogger("noc.vault")

class DecryptSecretRequest(BaseModel):
    name: str

class SaveSecretRequest(BaseModel):
    name: str
    type: str
    value: str

class DeleteSecretRequest(BaseModel):
    name: str

class ValidateCredentialRequest(BaseModel):
    type: str
    value: str

@router.get("")
async def api_get_vault(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Restrict vault visibility to Admin, Operator, and Engineer
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Vault access restricted."
        )
        
    secrets = VaultService.get_secrets(db)
    safe_secrets = {}
    for name, data in secrets.items():
        safe_secrets[name] = {
            "type": data["type"],
            "value": "****** [AES-256 Ciphertext]",
            "created_at": data.get("created_at"),
            "expires_at": data.get("expires_at"),
            "last_rotated": data.get("last_rotated"),
            "access_count": data.get("access_count", 0)
        }
    return safe_secrets


@router.post("/decrypt")
async def api_decrypt_secret(req: DecryptSecretRequest, request: Request, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Restrict decryption to Admin and Operator
    if user["role"] not in ["Admin", "Operator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Decryption permissions restricted."
        )
        
    name = req.name.strip()
    secret_value = VaultService.get_secret(db, name)
    if not secret_value:
        raise HTTPException(status_code=404, detail="Secret not found in vault.")
        
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Decrypt Vault Secret",
        ip=request.client.host if request.client else "0.0.0.0",
        details=f"Decrypted credential safe secret: '{name}'"
    )
    
    return {
        "name": name,
        "decryptedValue": secret_value
    }

@router.post("/add")
async def api_add_secret(req: SaveSecretRequest, request: Request, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Restrict secret addition to Admin and Operator
    if user["role"] not in ["Admin", "Operator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Vault modification restricted."
        )
        
    name = req.name.strip()
    secret_type = req.type.strip()
    value = req.value.strip()
    
    if not name or not secret_type or not value:
        raise HTTPException(status_code=400, detail="Missing secret parameters.")
        
    # Validate format before saving
    is_valid, errors = VaultService.validate_credential(secret_type, value)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Credential validation failed: {'; '.join(errors)}"
        )
        
    VaultService.add_secret(db, name, secret_type, value)
    
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Add Vault Secret",
        ip=request.client.host if request.client else "0.0.0.0",
        details=f"Added vaulted credential secret: '{name}' ({secret_type})"
    )
    
    return {"status": "success", "message": f"Credential secret '{name}' added successfully."}

@router.post("/delete")
async def api_delete_secret(req: DeleteSecretRequest, request: Request, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Delete credentials is strictly restricted to Admin role
    if user["role"] not in ["Admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Deleting credentials is restricted to Admin role only."
        )
        
    name = req.name.strip()
    deleted = VaultService.delete_secret(db, name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Secret not found.")
        
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Delete Vault Secret",
        ip=request.client.host if request.client else "0.0.0.0",
        details=f"Deleted vaulted credential secret: '{name}'"
    )
    return {"status": "success", "message": f"Credential secret '{name}' deleted successfully."}

@router.post("/test", response_model=CredentialTestResponse)
async def api_test_credential(req: CredentialTestRequest, request: Request, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Admin, Operator, and Engineer can test credentials
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Credential testing restricted."
        )
        
    success, message, test_logs = VaultService.test_credential_connection(db, req.name, req.device)
    
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Test Vault Credential",
        ip=request.client.host if request.client else "0.0.0.0",
        details=f"Tested credential '{req.name}' on '{req.device}'. Status: {'PASSED' if success else 'FAILED'}"
    )
    
    return {
        "success": success,
        "message": message,
        "logs": test_logs
    }

@router.post("/validate", response_model=CredentialValidationResponse)
async def api_validate_credential(req: ValidateCredentialRequest, user: dict = Depends(get_current_user)):
    # Any authorized user (Admin, Operator, Engineer) can validate formats
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Validation endpoints restricted."
        )
        
    valid, errors = VaultService.validate_credential(req.type, req.value)
    return {
        "valid": valid,
        "errors": errors
    }
