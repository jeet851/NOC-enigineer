# Enterprise Structured Logging

The application implements high-performance structured logging. It emits logs as single-line JSON objects to files and streams, allowing seamless ingestion into collectors like ELK, Splunk, or Datadog.

## Logging Structure

Every log message is serialized as a JSON string with the following fields:

```json
{
  "timestamp": "2026-07-11T07:22:14.928Z",
  "level": "INFO",
  "logger": "noc.telemetry",
  "module": "collector",
  "function": "run_network_telemetry_loop",
  "line": 41,
  "message": "Zero-Trust Monitoring Engine active",
  "context": {
    "interval_seconds": 5
  }
}
```

## Logging Outputs

1. **Stdout Stream**: Emits logs directly to standard output. In `development` mode, stdout logs are colored and pretty-printed for readability. In `production` mode, stdout logs are formatted as raw JSON.
2. **Rotating File Log**: All logs are written to the directory specified by `LOG_DIR` (default: `./logs/`) in `noc_copilot.log`. Files rotate automatically when they reach `LOG_MAX_BYTES` (default: 10MB), retaining a count defined by `LOG_BACKUP_COUNT`.

## Logger Namespaces

Isolate log streams using the following namespaces:

- `noc.startup`: Boot sequence, dependency checks, and database seeding status.
- `noc.api`: Endpoint routing, request latency, and HTTP errors.
- `noc.auth`: Session generation, MFA code validation, and token rotations.
- `noc.ai`: Prompt submissions, Gemini API calls, and validation results.
- `noc.telemetry`: Device performance collection scans and alert triggers.
- `noc.incident`: Incident investigations and remediation playbooks.
- `noc.automation`: SSH device logins, commands execution, and playbook runs.
- `noc.websocket`: Real-time dashboard updates and client connect/disconnect events.
- `noc.redis`: Redis pings, keys cache reads, and fallback activations.
- `noc.vault`: Credentials encrypt/decrypt and SSH rotation audits.
- `noc.security`: Blocked requests, brute-force detections, and safety policy triggers.
