# Database Migrations (Alembic)

Database schema upgrades are managed via Alembic. This document details how to apply, generate, and rollback schema versions.

## Setup & Configuration

Alembic configuration is stored in `alembic.ini` and uses metadata from the SQLAlchemy models dynamically registered in `models/__init__.py`.

The target database endpoint is loaded directly from settings (`DATABASE_URL`) inside `alembic/env.py`.

## Common Commands

### 1. Check current migration state
```bash
alembic current
```

### 2. List migration history
```bash
alembic history --verbose
```

### 3. Upgrade to the latest schema version
```bash
alembic upgrade head
```

### 4. Downgrade schema by 1 step
```bash
alembic downgrade -1
```

### 5. Generate a new database migration automatically
If you modify fields or add tables to the ORM classes inside the `models/` directory, generate a new version using:
```bash
alembic revision --autogenerate -m "description of changes"
```

## Troubleshooting

### Connection Timeout
If you encounter timeout errors when upgrading PostgreSQL schemas, check that `settings.DATABASE_URL` is correct and that the database server is running and reachable.

### Eager migrations in SQLite
SQLite has limited support for column alterations (e.g. adding columns with foreign key constraints). Alembic is configured to use batch operations automatically where possible. If SQLite migrations fail, recreate the db file `noc_local.db` in development mode.
