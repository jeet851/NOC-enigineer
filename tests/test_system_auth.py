import pytest
from fastapi.testclient import TestClient

def test_full_login_mfa_refresh_logout_lifecycle(client: TestClient):
    # 1. Login attempt with invalid password
    login_fail_payload = {"username": "admin", "password": "wrongpassword"}
    response = client.post("/api/login", json=login_fail_payload)
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]
    
    # 2. Login attempt with valid password -> triggers MFA Challenge
    login_payload = {"username": "admin", "password": "admin123"}
    response = client.post("/api/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["otpRequired"] is True
    assert "challengeId" in data
    assert "simulatedOtp" in data
    
    challenge_id = data["challengeId"]
    simulated_otp = data["simulatedOtp"]
    
    # 3. Verify OTP with incorrect OTP
    verify_fail_payload = {"challengeId": challenge_id, "otp": "000000"}
    response = client.post("/api/verify-otp", json=verify_fail_payload)
    assert response.status_code == 401
    assert "Invalid OTP code" in response.json()["detail"]
    
    # 4. Verify OTP with correct OTP -> returns tokens
    verify_payload = {"challengeId": challenge_id, "otp": simulated_otp}
    response = client.post("/api/verify-otp", json=verify_payload)
    assert response.status_code == 200
    token_data = response.json()
    assert "accessToken" in token_data
    assert "refreshToken" in token_data
    assert token_data["user"]["username"] == "admin"
    assert token_data["user"]["role"] == "Admin"
    
    access_token = token_data["accessToken"]
    refresh_token = token_data["refreshToken"]
    
    # 5. Access protected route with missing authorization header
    response = client.get("/api/vault")
    assert response.status_code == 401
    
    # 6. Access protected route with valid token
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/vault", headers=headers)
    assert response.status_code == 200
    
    # 7. Refresh token exchange
    refresh_payload = {"refreshToken": refresh_token}
    response = client.post("/api/refresh", json=refresh_payload)
    assert response.status_code == 200
    new_token_data = response.json()
    assert "accessToken" in new_token_data
    assert "refreshToken" in new_token_data
    
    new_access_token = new_token_data["accessToken"]
    new_refresh_token = new_token_data["refreshToken"]
    
    # Verify new access token works
    new_headers = {"Authorization": f"Bearer {new_access_token}"}
    response = client.get("/api/vault", headers=new_headers)
    assert response.status_code == 200
    
    # Verify old refresh token is revoked (rotation check)
    response = client.post("/api/refresh", json={"refreshToken": refresh_token})
    assert response.status_code == 401
    assert "expired, revoked, or invalid" in response.json()["detail"]
    
    # 8. Logout
    logout_response = client.post("/api/logout", headers=new_headers)
    assert logout_response.status_code == 200
    assert logout_response.json() == {"status": "success"}
    
    # Verify refreshed token no longer works for refresh since session was cleared
    response = client.post("/api/refresh", json={"refreshToken": new_refresh_token})
    assert response.status_code == 401
