# ==========================================
# STAGE 1: Build & Dependency compilation
# ==========================================
FROM python:3.11-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ==========================================
# STAGE 2: Secure running environment
# ==========================================
FROM python:3.11-slim as runner

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"

# Install runtime utilities (e.g. sqlite3, openssl for cert diagnostics)
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual env and code from builder
COPY --from=builder /opt/venv /opt/venv
COPY . .

# Setup non-root execution user for security compliance
RUN groupadd -g 10001 nocgroup \
    && useradd -u 10001 -g nocgroup -s /bin/bash nocuser \
    && chown -R nocuser:nocgroup /app

USER nocuser

EXPOSE 5001

CMD ["uvicorn", "fastapi_server:app", "--host", "0.0.0.0", "--port", "5001", "--ssl-keyfile", "localhost.key", "--ssl-certfile", "localhost.crt"]
