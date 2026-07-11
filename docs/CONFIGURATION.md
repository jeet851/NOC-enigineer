# Configuration Reference

The NOC Copilot application is configured using Pydantic Settings. Settings are loaded from environment variables or a `.env` file in the project root directory.

## Core Settings

| Name | Type | Default | Description |
|---|---|---|---|
| `APP_ENV` | `str` | `development` | Environment mode (`development`, `testing`, `production`). In production, a valid `JWT_SECRET_KEY` is required. |
| `DEBUG` | `bool` | `False` | Enable debug logs and detailed validation error formats. Must be `False` in production. |
| `BIND_HOST` | `str` | `127.0.0.1` | Restricts access. Set to `0.0.0.0` to listen on all interfaces. |
| `PORT` | `int` | `5001` | Port number to bind the uvicorn web server. |

## Database Configurations

| Name | Type | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | `str` | `sqlite:///./noc_local.db` | Target database connection URI. E.g., `postgresql://user:pass@host:5432/dbname`. |
| `DB_POOL_SIZE` | `int` | `10` | SQLAlchemy sync connection pool size (ignored for SQLite). |
| `DB_MAX_OVERFLOW` | `int` | `20` | Max overflow database connections (ignored for SQLite). |

## Redis Cache & Worker Configurations

| Name | Type | Default | Description |
|---|---|---|---|
| `REDIS_URL` | `str` | `redis://localhost:6379/0` | Connection URL for Redis key-value cache store. |
| `REDIS_SOCKET_TIMEOUT` | `float` | `0.5` | Max connection read timeout in seconds before fallback. |
| `REDIS_KEY_PREFIX` | `str` | `NOC:` | Namespace prefix prepended to all Redis keys. |
| `REDIS_CACHE_TTL_SECONDS`| `int` | `3` | Cache expiration for dashboard telemetry updates. |
| `RABBITMQ_URL` | `str` | `amqp://guest:guest@localhost:5672//` | Broker URL for Celery worker tasks. |

## Security & Authentication

| Name | Type | Default | Description |
|---|---|---|---|
| `JWT_SECRET_KEY` | `str` | *None* | Symmetric key used to sign session tokens. **Must be overridden in production.** |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `int` | `60` | Expiration lifetime of an generated API access token. |
| `RATE_LIMIT_PER_MINUTE` | `int` | `60` | Global slowapi rate limit (requests/minute) per client IP. |
| `RATE_LIMIT_AUTH_PER_MINUTE`| `int` | `10` | Stricter rate limit for login and OTP endpoints. |

## AI Engine (Google Gemini)

| Name | Type | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | `str` | *None* | Google Gemini API secret key. If empty, the app falls back to simulated template diagnostics. |
| `GEMINI_MODEL` | `str` | `gemini-1.5-flash` | LLM model version used for sweep analysis and root cause identification. |
| `AI_CONFIDENCE_AUTONOMOUS_THRESHOLD` | `float` | `95.0` | Minimum confidence score to execute auto-remediation playbooks. |
