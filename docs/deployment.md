# Deployment & Scaling

## Docker Setup

### API Dockerfile (`Dockerfile`)

Multi-stage build:
- **builder**: Install deps from `pyproject.toml`
- **runner**: Slim Python image, curl for healthcheck, non-root `app` user, ports 8000+8001, HEALTHCHECK, 4 uvicorn workers

### Frontend Dockerfile (`infra/docker/Dockerfile.frontend`)

Three-stage:
- **deps**: `npm ci`
- **builder**: `next build`
- **runner**: `node:20-alpine`, standalone output, non-root `nextjs` user, HEALTHCHECK

### Docker Compose (`docker-compose.yml`)

Full stack with resource limits:

```yaml
services:
  postgres:     # pgvector/pgvector:pg17, healthcheck, 1G limit
  redis:        # redis:7-alpine, AOF, LRU, 512M limit, healthcheck
  api:          # built from ., 4 workers, 1G/1CPU limit, depends on postgres+redis
  frontend:     # Next.js, 512M/0.5CPU limit
```

### Production Override (`infra/docker/docker-compose.prod.yml`)

Swarm-mode:
- Rolling update: `start-first`, parallelism 1, delay 10s
- Rollback: `stop-first`, delay 5s
- Placement constraints
- Configurable replica counts

### Monitoring Stack (`infra/docker/docker-compose.monitoring.yml`)

```yaml
services:
  prometheus:    # 30d retention, lifecycle API, 1G limit
  grafana:       # Auto-provisioned datasource + dashboard, 512M limit
  node_exporter: # Global mode
  cadvisor:      # Global mode, privileged
```

## CI/CD Pipelines

### CI (`ci.yml`)

Triggers: push/PR to `main`, `develop`

```
Lint (ruff) → Test (pytest, pgvector service)
  → Build & Cache (Docker Buildx, GHA cache)
  → Security (Trivy scan)
  → Compose validation
```

### Deploy Dev (`deploy-dev.yml`)

Trigger: push to `develop`

```
Docker login (GHCR) → Build & push :dev-${sha}
  → Kustomize image tag update → kubectl apply to dev namespace
```

### Deploy Prod (`deploy-prod.yml`)

Trigger: `workflow_dispatch` with version tag, or release published

```
Validate version → Docker pull & verify
  → Deploy (kustomize apply, namePrefix: prod-)
  → Health check → Slack notification on failure
```

## Environment Configs

| File | Environment | Key Differences |
|------|-------------|----------------|
| `.env.example` | Development | Default localhost, debug ON |
| `infra/env/development.env` | Development | All env vars, DEBUG=true |
| `infra/env/staging.env` | Staging | Lower rate limits (120/min), less verbose |
| `infra/env/production.env` | Production | SSL-only HIKER_URL, 600 rate limit, Prometheus ON |

## Kubernetes Manifests (`infra/k8s/`)

| File | Resource | Details |
|------|----------|---------|
| `configmap.yaml` | ConfigMap | API + frontend non-sensitive env vars |
| `secrets.yaml` | Secret | DB URL, JWT, admin hash, API token, OpenAI key |
| `api-deployment.yaml` | Deployment | 3 replicas, rolling update, probes, 256M/0.25CPU → 1G/1CPU |
| `api-hpa.yaml` | HPA | 70% CPU + 70% memory, min 3 / max 10 |
| `api-service.yaml` | Service | ClusterIP, port 8000+8001, prom scrape annotations |
| `frontend-deployment.yaml` | Deployment | 3 replicas, probes, 128M/0.1CPU → 512M/0.5CPU |
| `frontend-service.yaml` | Service | ClusterIP port 3000 |
| `redis-deployment.yaml` | StatefulSet | 1 replica, AOF, 512MB LRU, 1GB PVC, healthcheck |
| `redis-service.yaml` | Service | ClusterIP port 6379 |
| `hpa.yaml` | HPA | Frontend HPA + API HPA |
| `ingress.yaml` | Ingress | TLS, nginx, cert-manager, routes to api + frontend |
| `kustomization.yaml` | Kustomize | Dev/staging overlay with namePrefix + replica counts |

## Rollback Strategy

### Docker Swarm

```bash
docker service update --rollback vids-clone_api
docker service update --rollback vids-clone_frontend
```

### Kubernetes

```bash
# Rollback to previous revision
kubectl rollout undo deployment/api -n vids-clone-prod

# Rollback to specific revision
kubectl rollout undo deployment/api -n vids-clone-prod --to-revision=3

# Check rollout status
kubectl rollout status deployment/api -n vids-clone-prod
```

### Script

`scripts/rollback.sh` — detects k8s or docker-compose and performs appropriate rollback.

## Scaling Strategies

### Connection Pooling

- `asyncpg.create_pool(min_size=2, max_size=20, max_queries=50000, max_inactive_connection_lifetime=3600)`
- Neon: append `?pooled=true` to DATABASE_URL for PgBouncer-managed pooling

### Redis Caching

- Session data: TTL 300s
- Session list: TTL 120s
- Cache-aside pattern with invalidate-on-write
- LRU eviction policy, 512MB maxmemory
- Null-safe: Redis unavailability doesn't crash the app

### Horizontal Pod Autoscaling (K8s)

```yaml
# API: 70% CPU + 70% memory, 2–10 pods
# Frontend: 70% CPU, 2–10 pods
scaleUp:
  stabilizationWindowSeconds: 60
  policies:
    - type: Percent
      value: 100
      periodSeconds: 60
scaleDown:
  stabilizationWindowSeconds: 300
```

### CDN (Recommended)

- Frontend static assets: Vercel Edge Network or Cloudflare
- Video files: served from Hiker CDN (no local video storage)
- API responses: Cloudflare cache for GET endpoints with `s-maxage` headers

### Resource Limits

Prevent noisy-neighbor problems:

| Service | Request | Limit |
|---------|---------|-------|
| API | 256M / 250m CPU | 1G / 1 CPU |
| Frontend | 128M / 100m CPU | 512M / 500m CPU |
| Postgres | — | 1G |
| Redis | — | 512M |
| Prometheus | — | 1G |
| Grafana | — | 512M |

## Secrets Management

### Docker Compose

```
.env file (git-ignored) loaded via docker-compose.yml env_file directive
```

### Kubernetes

- `api-secrets.yaml`: encrypted via sealed-secrets (template placeholders shown)
- Production secrets stored in GitHub Actions secrets → injected via workflow
- Never commit secrets to the repository

### Required Secrets

| Secret | Where Used |
|--------|-----------|
| `JWT_SECRET` | API token signing |
| `DATABASE_URL` | DB connection (Neon) |
| `ADMIN_PASSWORD_HASH` | Admin auth (PBKDF2) |
| `HIKER_API_TOKEN` | Hiker API |
| `OPENAI_API_KEY` | LLM calls |
| `SLACK_WEBHOOK_URL` | Deploy notifications |
| `GHCR_PAT` | Docker registry |
| `KUBECONFIG` | Kubernetes access |
