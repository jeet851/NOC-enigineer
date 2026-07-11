# API Endpoints Reference

The NOC Copilot exposes a comprehensive REST and WebSocket interface.

## Endpoint Categories

### 1. Authentication (`/api`)
- `POST /api/login` - Initiate MFA login challenge (issues challenge ID).
- `POST /api/verify-otp` - Validate challenge OTP and issue JWT access/refresh tokens.
- `POST /api/refresh` - Rotate and issue new access/refresh tokens.
- `POST /api/logout` - Invalidate active session tokens.

### 2. Copilot Chat (`/api`)
- `GET /api/personas` - List available domain experts (NOC Engineer, Security Analyst, etc.).
- `POST /api/chat` - Submit a message to the AI copilot (with context correlation).
- `POST /api/chat/stream` - SSE streaming chat channel.

### 3. Configuration Management (`/api`)
- `POST /api/validate-config` - Runs command syntax checks and AI safety sweeps.
- `POST /api/deploy-config` - Deploys configurations to network nodes via playbooks.

### 4. Telemetry & Devices (`/api`)
- `GET /api/telemetry` - Retrieve unified dashboard metrics, node statuses, and alarms.
- `GET /api/devices` - Query list of inventoried network devices.
- `GET /api/devices/{name}/interfaces` - Retrieve interface speeds and status links.

### 5. Incidents & Healing (`/api/incidents`)
- `GET /api/incidents` - List all incident records.
- `GET /api/incidents/active` - List active alert investigations.
- `POST /api/incidents/{incident_id}/resolve` - Manually mark an incident as resolved.

### 6. Subnet Discovery (`/api/discovery`)
- `POST /api/discovery/run` - Trigger an immediate background discovery scan.
- `POST /api/discovery/schedule` - Schedule a recurring discovery cycle.

### 7. Credential Vault (`/api/vault`)
- `GET /api/vault` - List encrypted secret metadata.
- `POST /api/vault/add` - Store a new credential (validates complexity).
- `POST /api/vault/decrypt` - Retrieve raw credential value (restricted to Admin/Operator).
- `POST /api/vault/delete` - Remove vault records.
- `POST /api/vault/test` - Test credential connection to remote device.

### 8. System Monitoring (`/api/monitoring`)
- `GET /api/monitoring/health` - Retrieve CPU, RAM, disk partitions, and system health status.
- `POST /api/monitoring/simulate` - Toggle high-scale mode (10k devices, 1M events).

### 9. Zero-Trust Controls (`/api/zero-trust`)
- `POST /api/zero-trust/rotate-ssh` - Create and swap SSH key pairs.
- `POST /api/zero-trust/validate-certificate` - Audit TLS/SSL x509 expiration.
- `POST /api/zero-trust/update-role` - Modify user roles dynamically (restricted to Admin).
