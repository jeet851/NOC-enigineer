import pytest
from datetime import timedelta
from jose import jwt
from fastapi import HTTPException
from api.config import settings
from services.auth import (
    verify_password,
    get_password_hash,
    validate_password_strength,
    create_access_token,
    decode_token,
    generate_totp_secret,
    get_totp_token,
    verify_totp_token
)

def test_password_hashing_and_verification():
    raw_pwd = "MySecurePassword123!"
    hashed_pwd = get_password_hash(raw_pwd)
    
    assert verify_password(raw_pwd, hashed_pwd) is True
    assert verify_password("WrongPassword123!", hashed_pwd) is False

def test_password_strength_validation():
    # Strong password
    is_strong, errors = validate_password_strength("Abcd!1234")
    assert is_strong is True
    assert len(errors) == 0
    
    # Short password
    is_strong, errors = validate_password_strength("Ab1!")
    assert is_strong is False
    assert any("at least 8 characters" in e for e in errors)
    
    # No uppercase
    is_strong, errors = validate_password_strength("abcd!1234")
    assert is_strong is False
    assert any("uppercase" in e for e in errors)
    
    # No lowercase
    is_strong, errors = validate_password_strength("ABCD!1234")
    assert is_strong is False
    assert any("lowercase" in e for e in errors)
    
    # No digit
    is_strong, errors = validate_password_strength("Abcd!efgh")
    assert is_strong is False
    assert any("digit" in e for e in errors)
    
    # No special char
    is_strong, errors = validate_password_strength("Abcd12345")
    assert is_strong is False
    assert any("special character" in e for e in errors)

def test_jwt_creation_and_decoding():
    payload = {"sub": "admin", "role": "Admin", "name": "System Admin"}
    token = create_access_token(payload, expires_delta=timedelta(minutes=15))
    
    decoded = decode_token(token)
    assert decoded["sub"] == "admin"
    assert decoded["role"] == "Admin"
    assert decoded["name"] == "System Admin"

def test_jwt_invalid_or_expired():
    # Test completely invalid signature or payload
    with pytest.raises(HTTPException) as exc_info:
        decode_token("completely.invalid.token")
    assert exc_info.value.status_code == 401
    
    # Test expired token
    payload = {"sub": "test", "role": "Admin"}
    token = create_access_token(payload, expires_delta=timedelta(seconds=-10))
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token)
    assert exc_info.value.status_code == 401

def test_totp_generation_and_verification():
    secret = generate_totp_secret()
    assert len(secret) == 16
    
    # Generate TOTP code for secret
    code = get_totp_token(secret)
    assert len(code) == 6
    assert code.isdigit()
    
    # Verify TOTP code
    assert verify_totp_token(secret, code) is True
    
    # Verify wrong secret or code
    assert verify_totp_token(secret, "000000") is False
    assert verify_totp_token("INVALIDSECRET123", code) is False
