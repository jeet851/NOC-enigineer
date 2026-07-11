# Security Architecture & Hardening

The application conforms to Zero-Trust Security guidelines (NIST SP 800-207). It implements strict authentication, cryptographic segregation of secrets, role-based access control, and endpoint protections.

## Zero-Trust Security Measures

### 1. Multi-Factor Authentication (MFA)
- Every login request undergoes an MFA check.
- The authentication route `/api/login` issues an encrypted challenge ID and computes a time-based OTP (TOTP, RFC 6238).
- The client must immediately submit the matching OTP via `/api/verify-otp` to obtain access/refresh tokens.

### 2. Cryptographic Secret Vault
- Device credentials and private keys are never stored in raw plaintext inside the database.
- The `VaultService` encrypts values at rest using AES-256 (Fernet) cryptography.
- Keys are rotated programmatically via secure administrative API calls.

### 3. Role-Based Access Control (RBAC)
Routes are guarded using dependency checks that match user claims against a permissions matrix:

| Role | Allowed Actions |
|---|---|
| **Admin** | Full administrative rights, delete vault secrets, rotate keys, update user roles. |
| **Manager** / **Operator** | Run automation playbooks, trigger subnet discoveries, manually resolve incidents. |
| **Network Engineer** | Write configurations, view active incidents, validate syntax. Cannot deploy without dual approval if destructive actions are detected. |
| **Guest** / **Read Only** | Read metrics and logs. Blocked from executing commands or modifying configs. |

### 4. API Security Hardening
- **Rate Limiting**: Integrated `slowapi` checks route hits per client IP. Critical auth routes are strictly throttled.
- **Client IP Extraction**: The real client IP (`request.client.host`) is captured and stored in audit logs instead of localhost fallbacks.
- **Security Headers**: Mounts standard security headers to all HTTP responses:
  - `Content-Security-Policy`: Restricts scripts and fonts (tightened in production).
  - `X-Frame-Options: DENY`: Protects against clickjacking.
  - `X-Content-Type-Options: nosniff`: Prevents MIME-sniffing.
  - `Strict-Transport-Security`: Enforces HTTPS access.
  - `Permissions-Policy`: Disables device sensor access (microphone, camera, location).
