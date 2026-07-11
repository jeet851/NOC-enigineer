# Production Deployment & Disaster Recovery Guide

This document guides operations teams in deploying, monitoring, backing up, and recovering the AIOps NOC Dashboard in a production environment.

---

## 1. Container Deployments (Docker Compose)

For single-node staging or standalone deployments, use the multi-service Docker Compose configuration.

### Deployment Checklist:
1. Ensure ports `80`, `443`, `3000`, `9090`, and `15672` are open on the firewall.
2. Copy SSL/TLS production keys to `./deploy/certs/localhost.key` and `./deploy/certs/localhost.crt`.
3. Launch the container orchestration stack:
   ```bash
   cd deploy
   docker-compose up -d --build
   ```
4. Verify all container services are running:
   ```bash
   docker-compose ps
   ```

---

## 2. Kubernetes Clustering (Production scale-out)

For high-availability, multi-replica container orchestration, deploy to a Kubernetes cluster.

### Setup Steps:
1. **Provision Persistent Volumes**:
   Ensure a StorageClass supporting `ReadWriteMany` (like NFS or EFS) is configured in your cluster for SQLite shared access.
2. **Apply Stateful Backends (Redis, RabbitMQ)**:
   ```bash
   kubectl apply -f deploy/k8s/k8s-statefulsets.yaml
   ```
3. **Deploy FastAPI App & Celery Workers**:
   ```bash
   kubectl apply -f deploy/k8s/k8s-app.yaml
   kubectl apply -f deploy/k8s/k8s-workers.yaml
   ```
4. **Expose routing (Ingress & TLS)**:
   Ensure `cert-manager` is installed in the cluster to automatically provision TLS certificates:
   ```bash
   kubectl apply -f deploy/k8s/ingress.yaml
   ```

---

## 3. CI/CD Integration (GitHub Actions)

A GitHub Actions pipeline handles automated releases on pushing commits to the `main` branch.

### Prerequisites:
Configure the following secrets in your GitHub repository under **Settings > Secrets and variables > Actions**:
* `KUBECONFIG`: The raw YAML kubeconfig file for authenticated Kubernetes API access.

---

## 4. Monitoring & Logs

### Metrics Scraping (Prometheus & Grafana):
* **Prometheus**: Listens on port `9090` scraping endpoints (`/api/health`) automatically.
* **Grafana**: Available on port `3000`. Configure a new Prometheus Data Source (`http://noc_prometheus:9090`) and import performance dashboards.

### Log shipping (Elastic Stack / EFK):
Filebeat automatically harvests system syslogs at `/app/syslogs.log` and Nginx requests inside container volumes, forwarding them to Elasticsearch (`http://elasticsearch:9200`).

---

## 5. Automated Backups & Restore

### Database Backup cron job:
Install a cron job on the deployment node or pod to perform backups every 6 hours:
```cron
0 */6 * * * /bin/bash /app/deploy/scripts/backup_db.sh >> /var/log/noc_db_backup.log 2>&1
```

### Database Restoration:
To restore the database from a backup point (e.g. `noc_db_backup_20260705_120000.db.gz`):
```bash
/bin/bash /app/deploy/scripts/restore_db.sh noc_db_backup_20260705_120000.db.gz
```

---

## 6. Disaster Recovery Plan (DRP)

### Metrics targets:
* **Recovery Point Objective (RPO)**: **6 hours** (maximum data loss window between backup crons).
* **Recovery Time Objective (RTO)**: **15 minutes** (maximum service interruption window).

### System Outage Failover Procedures:
1. **Primary Node Outage**:
   If the hosting VM hosting Docker Compose crashes, spin up a secondary failover instance, clone the repo, pull the latest database file from S3, run `restore_db.sh`, and launch compose services.
2. **Kubernetes Pod Failures**:
   The deployment spec implements self-healing replicas. Liveness probes automatically restart crashed containers.
3. **Database Corruptions**:
   If integrity checks fail, stop the application services, execute the restoration script to restore the latest S3 backup, verify SQLite pragma checks, and boot the stack.
