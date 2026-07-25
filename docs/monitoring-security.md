# Monitoring & Security

## Monitoring

### Logging (`app/logging_setup.py`)

Structured JSON logging via `structlog`:

```json
{"event": "request_completed", "request_id": "uuid", "method": "GET",
 "path": "/health", "status_code": 200, "elapsed_ms": 15.2,
 "level": "info", "timestamp": "2025-01-01T00:00:00.000Z"}
```

Configuration:
- Production: `INFO` level
- Development: `DEBUG` level
- Processors: TimeStamper (ISO), JSONRenderer
- Standard library logging also configured for third-party compatibility

### Audit Logging (`AuditLogMiddleware`)

Triggers on sensitive operations (`POST`, `PUT`, `PATCH`, `DELETE` on paths starting with `/auth/`, `/session/`, `/agent/chat`, `/agent/ws`, `/pipeline/run`):

```json
{"event": "audit_action", "request_id": "uuid", "method": "POST",
 "path": "/agent/chat", "status_code": 200,
 "client_ip": "203.0.113.42", "level": "info", "timestamp": "..."}
```

### Prometheus Metrics (port 8001, separate from API)

43 total metrics across 7 categories:

**Pipeline Metrics** (9):
- `pipeline_runs_total{status}`
- `pipeline_run_duration_seconds{status}`
- `pipeline_stage_duration_seconds{stage, status}`
- `pipeline_stage_errors_total{stage}`
- `pipeline_stage_status{stage, status}`
- `pipeline_last_run_timestamp{status}`
- `pipeline_last_run_duration_seconds{status}`
- `pipeline_scheduler_running`
- `pipeline_scheduler_consecutive_failures`

**Analytics Metrics** (5):
- `analytics_runs_total{status}`
- `analytics_run_duration_seconds`
- `analytics_errors_total{error_type}`
- `analytics_last_run_timestamp`
- `analytics_last_run_duration_seconds`

**Content Intelligence Metrics** (5):
- `content_intelligence_runs_total{status}`
- `content_intelligence_run_duration_seconds`
- `content_intelligence_errors_total{error_type}`
- `content_intelligence_last_run_timestamp`
- `content_intelligence_last_run_duration_seconds`

**Creator Intelligence Metrics** (5):
- `creator_intelligence_runs_total{status}`
- `creator_intelligence_run_duration_seconds`
- `creator_intelligence_errors_total{error_type}`
- `creator_intelligence_last_run_timestamp`
- `creator_intelligence_last_run_duration_seconds`

**HTTP/DB/Auth Metrics** (5):
- `http_requests_total{method, endpoint, status}`
- `http_request_duration_seconds{method, endpoint}`
- `db_queries_total{operation}`
- `db_query_duration_seconds{operation}`
- `auth_attempts_total{result}`

**LLM Metrics** (2):
- `llm_requests_total{provider, model, status}`
- `llm_request_duration_seconds{provider}`

**Agent Metrics** (5):
- `agent_invocations_total{mode}`
- `agent_invocation_duration_seconds{mode}`
- `agent_errors_total{mode}`
- `agent_confidence_bucket{bucket}`

### Grafana

Provisioned dashboard (`grafana/dashboard.json`) with 22 panels:
- Pipeline run count, duration, stage breakdown
- HTTP request rate, latency (p50/p95/p99)
- DB query rate and latency
- LLM request rate, latency, error rate
- Agent invocation count, duration, confidence distribution
- Content/creator intelligence pipeline metrics
- System resources (via node_exporter + cadvisor)

Auto-provisioned datasource (`grafana/datasources.yml`) pointing to Prometheus at `http://prometheus:9090`.

### Alerts (`prometheus/alerts.yml`)

9 alert rules:

| Alert | Condition | Severity |
|-------|-----------|----------|
| HighPipelineFailureRate | `rate(pipeline_runs_total{status="failed"}[15m]) > 0` | critical |
| StageFailure | `pipeline_stage_errors_total > 0` | warning |
| HighLLMErrorRate | `rate(llm_requests_total{status=~"http_4.."}[15m]) > 0.1` | critical |
| HighHTTPErrorRate | `rate(http_requests_total{status=~"5.."}[15m]) > 0.05` | critical |
| HighHTTPLatency | `histogram_quantile(0.95, http_request_duration_seconds) > 2` | warning |
| APIDown | `up{job="api"} == 0` | critical |
| LowConfidence | `agent_confidence_bucket{bucket="low"} == 1 over 1h` | warning |
| AgentErrors | `rate(agent_errors_total[15m]) > 0` | warning |
| SchedulerStopped | `pipeline_scheduler_running == 0` | critical |

## Security Hardening

### HTTPS Enforcement (`HTTPSEnforcementMiddleware`)

In production, all requests must come through `X-Forwarded-Proto: https`. HTTP requests return `426 Upgrade Required`.

### JWT Authentication

- Algorithm: `HS256`
- Expiration: configurable via `JWT_EXPIRE_MINUTES` (default 60)
- Token issued via `POST /auth/token` with admin credentials
- Password: PBKDF2-SHA256 with 16-byte random salt, 100,000 iterations

### Security Headers (`SecurityHeadersMiddleware`)

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Strict-Transport-Security: max-age=31536000; includeSubDomains   (production)
Content-Security-Policy: default-src 'self'; script-src 'self';   (production)
                         style-src 'self' 'unsafe-inline';
                         img-src 'self' data:; font-src 'self'
```

### Rate Limiting (`slowapi`)

- Default: 60 requests/minute (development) or configurable (`RATE_LIMIT_PER_MINUTE`)
- Keyed by remote IP address
- Enabled only in production
- Returns `429 Too Many Requests` when exceeded

### Input Validation (`InputValidationMiddleware`)

- Max request body: 1MB
- Max path length: 512 characters
- Returns `413 Payload Too Large` or `414 URI Too Long`

### CSRF Protection

- Not applicable for stateless JWT API
- Frontend uses `Authorization` header (not cookies)

### CORS

- Currently allows all origins (`allow_origins=["*"]`)
- Restrict in production to specific frontend domains

### Secrets & Credentials

- Never logged: passwords, tokens, secrets
- JWT secret validated before token operations
- Database credentials loaded from environment, never hardcoded
- Kubernetes secrets via sealed-secrets
- GitHub Actions secrets for CI/CD

### Dependency Vulnerability Scanning

- `Trivy` in CI pipeline scans container images
- Regular `pip audit` / `npm audit` recommended
- All dependencies version-pinned in `pyproject.toml` and `package.json`
