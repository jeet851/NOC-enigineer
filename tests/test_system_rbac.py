import pytest
from fastapi.testclient import TestClient

def get_auth_headers(client: TestClient, username: str, password: str) -> dict:
    login_payload = {"username": username, "password": password}
    response = client.post("/api/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    challenge_id = data["challengeId"]
    simulated_otp = data["simulatedOtp"]
    
    verify_payload = {"challengeId": challenge_id, "otp": simulated_otp}
    response = client.post("/api/verify-otp", json=verify_payload)
    assert response.status_code == 200
    token = response.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}

def test_rbac_vault_visibility(client: TestClient):
    # Admin should access vault
    admin_headers = get_auth_headers(client, "admin", "admin123")
    response = client.get("/api/vault", headers=admin_headers)
    assert response.status_code == 200
    
    # Operator should access vault
    operator_headers = get_auth_headers(client, "operator", "operator123")
    response = client.get("/api/vault", headers=operator_headers)
    assert response.status_code == 200
    
    # Engineer should access vault
    engineer_headers = get_auth_headers(client, "engineer", "engineer123")
    response = client.get("/api/vault", headers=engineer_headers)
    assert response.status_code == 200
    
    # Read Only should be denied
    readonly_headers = get_auth_headers(client, "read_only", "readonly123")
    response = client.get("/api/vault", headers=readonly_headers)
    assert response.status_code == 403
    assert "access restricted" in response.json()["detail"].lower()

def test_rbac_vault_decryption(client: TestClient):
    # Seed a secret first using Admin role
    admin_headers = get_auth_headers(client, "admin", "admin123")
    secret_payload = {"name": "TestDecryptionSecret", "type": "Password", "value": "my-secret-val-1"}
    client.post("/api/vault/add", json=secret_payload, headers=admin_headers)
    
    # Admin should be allowed to decrypt
    decrypt_payload = {"name": "TestDecryptionSecret"}
    response = client.post("/api/vault/decrypt", json=decrypt_payload, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["decryptedValue"] == "my-secret-val-1"
    
    # Operator should be allowed to decrypt
    operator_headers = get_auth_headers(client, "operator", "operator123")
    response = client.post("/api/vault/decrypt", json=decrypt_payload, headers=operator_headers)
    assert response.status_code == 200
    assert response.json()["decryptedValue"] == "my-secret-val-1"
    
    # Engineer should be denied decryption
    engineer_headers = get_auth_headers(client, "engineer", "engineer123")
    response = client.post("/api/vault/decrypt", json=decrypt_payload, headers=engineer_headers)
    assert response.status_code == 403
    assert "decryption permissions restricted" in response.json()["detail"].lower()
    
    # Read Only should be denied decryption
    readonly_headers = get_auth_headers(client, "read_only", "readonly123")
    response = client.post("/api/vault/decrypt", json=decrypt_payload, headers=readonly_headers)
    assert response.status_code == 403

def test_rbac_vault_deletion(client: TestClient):
    # Seed a secret first
    admin_headers = get_auth_headers(client, "admin", "admin123")
    secret_payload = {"name": "TestDeletionSecret", "type": "Password", "value": "my-secret-val-2"}
    client.post("/api/vault/add", json=secret_payload, headers=admin_headers)
    
    delete_payload = {"name": "TestDeletionSecret"}
    
    # Operator should be denied deletion
    operator_headers = get_auth_headers(client, "operator", "operator123")
    response = client.post("/api/vault/delete", json=delete_payload, headers=operator_headers)
    assert response.status_code == 403
    assert "deleting credentials is restricted" in response.json()["detail"].lower()
    
    # Engineer should be denied deletion
    engineer_headers = get_auth_headers(client, "engineer", "engineer123")
    response = client.post("/api/vault/delete", json=delete_payload, headers=engineer_headers)
    assert response.status_code == 403
    
    # Admin should be allowed to delete
    response = client.post("/api/vault/delete", json=delete_payload, headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": f"Credential secret '{delete_payload['name']}' deleted successfully."}
