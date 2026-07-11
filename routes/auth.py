from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
import uuid
import random
from datetime import datetime
from typing import Optional

from database.session import SessionLocal
from api.deps import get_db
from schemas.auth import LoginRequest, LoginOtpResponse, VerifyOtpRequest, LoginSuccessResponse, TokenRefreshRequest
from models.user import User
from models.token import UserRefreshToken
from services.auth import (
    verify_password, create_access_token, generate_refresh_token,
    save_refresh_token, verify_refresh_token, revoke_refresh_token,
    get_totp_token, verify_totp_token
)
from services.audit import AuditService

router = APIRouter(prefix="/api", tags=["authentication"])

from services.redis_cache import RedisCacheManager
import json

@router.post("/login", response_model=LoginOtpResponse)
async def api_login(req: LoginRequest, db: Session = Depends(get_db)):
    username = req.username.strip().lower()
    password = req.password.strip()
    
    # Query user from DB
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not verify_password(password, user.password_hash):
        # Audit log failed login
        AuditService.log_audit_event(
            db=db,
            user_name=username or "unknown",
            role="N/A",
            action="Login Attempt Failed",
            ip="127.0.0.1",
            details="Invalid password credentials.",
            status="Failed"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password credentials."
        )
        
    # Generate cryptographic time-based OTP using the user's totp_secret
    if not user.totp_secret:
        # Generate default one if missing
        from services.auth import generate_totp_secret
        user.totp_secret = generate_totp_secret()
        db.commit()
        
    otp = get_totp_token(user.totp_secret)
    challenge_id = str(uuid.uuid4())
    
    challenge_payload = {
        "username": username,
        "totp_secret": user.totp_secret,
        "timestamp": datetime.now().isoformat()
    }
    RedisCacheManager.set(f"challenge:{challenge_id}", json.dumps(challenge_payload), ex=300)
    
    return {
        "otpRequired": True,
        "challengeId": challenge_id,
        "simulatedOtp": otp
    }

@router.post("/verify-otp", response_model=LoginSuccessResponse)
async def api_verify_otp(req: VerifyOtpRequest, db: Session = Depends(get_db)):
    challenge_id = req.challengeId
    otp_code = req.otp.strip()
    
    challenge_str = RedisCacheManager.get(f"challenge:{challenge_id}")
    if not challenge_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Challenge context expired or invalid. Re-authenticate."
        )
        
    challenge = json.loads(challenge_str)
    # Cryptographically verify TOTP code
    if not verify_totp_token(challenge["totp_secret"], otp_code):
        AuditService.log_audit_event(
            db=db,
            user_name=challenge["username"],
            role="N/A",
            action="MFA Verification Failed",
            ip="127.0.0.1",
            details="Invalid OTP code entered.",
            status="Failed"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP code. Authentication failed."
        )

        
    username = challenge["username"]
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
         
    # Generate tokens
    token_data = {
        "sub": user.username,
        "role": user.role,
        "name": user.name
    }
    access_token = create_access_token(data=token_data)
    refresh_token = generate_refresh_token()
    
    # Save refresh token in DB
    save_refresh_token(db, user.id, refresh_token, expires_days=7)
    
    # Clean up challenge
    RedisCacheManager.delete(f"challenge:{challenge_id}")
    
    # Audit log success
    AuditService.log_audit_event(
        db=db,
        user_name=username,
        role=user.role,
        action="Login Successful",
        ip="127.0.0.1",
        details="Zero-Trust session initiated with Access + Refresh tokens."
    )
    
    return {
        "token": access_token, # Backward compatibility
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "user": {
            "username": user.username,
            "role": user.role,
            "name": user.name
        }
    }

@router.post("/refresh", response_model=LoginSuccessResponse)
async def api_refresh_token(req: TokenRefreshRequest, db: Session = Depends(get_db)):
    db_token = verify_refresh_token(db, req.refreshToken)
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is expired, revoked, or invalid."
        )
        
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token not found."
        )
        
    # Token Rotation: Revoke old and issue a new refresh token
    revoke_refresh_token(db, req.refreshToken)
    new_refresh_token = generate_refresh_token()
    save_refresh_token(db, user.id, new_refresh_token, expires_days=7)
    
    # Generate new access token
    token_data = {
        "sub": user.username,
        "role": user.role,
        "name": user.name
    }
    new_access_token = create_access_token(data=token_data)
    
    # Audit log the refresh
    AuditService.log_audit_event(
        db=db,
        user_name=user.username,
        role=user.role,
        action="Token Refreshed",
        ip="127.0.0.1",
        details="Access token regenerated via valid refresh token exchange."
    )
    
    return {
        "token": new_access_token,
        "accessToken": new_access_token,
        "refreshToken": new_refresh_token,
        "user": {
            "username": user.username,
            "role": user.role,
            "name": user.name
        }
    }

@router.post("/logout")
async def api_logout(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            from services.auth import decode_token
            payload = decode_token(token)
            username = payload.get("sub")
            role = payload.get("role")
            if username:
                # Find user and revoke all active refresh tokens upon logout
                user = db.query(User).filter(User.username == username).first()
                if user:
                    db.query(UserRefreshToken).filter(
                        UserRefreshToken.user_id == user.id,
                        UserRefreshToken.is_revoked == False
                    ).update({"is_revoked": True})
                    db.commit()
                    
                AuditService.log_audit_event(
                    db=db,
                    user_name=username,
                    role=role,
                    action="Logout Successful",
                    ip="127.0.0.1",
                    details="Session context destroyed. Active refresh tokens invalidated."
                )
        except Exception:
            pass
    return {"status": "success"}
