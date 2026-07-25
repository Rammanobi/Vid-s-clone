# Testing

## Test Framework

- **Python**: `pytest` + `pytest-asyncio` + `pytest-cov`
- **Frontend**: (planned) Jest + React Testing Library
- **Load testing**: Custom Locust-style agent test in `tests/load/test_agent.py`

## Running Tests

```bash
# All tests (excluding long-running API/OCR/CLIP/transcription tests)
pytest app/tests/ --ignore=app/tests/test_api.py --ignore=app/tests/test_ocr.py \
  --ignore=app/tests/test_clip.py --ignore=app/tests/test_transcription.py -v

# With coverage
pytest --cov=app --cov-report=term --cov-report=xml

# Specific test file
pytest app/tests/test_pipeline.py -v

# Load test (requires API running)
python tests/load/test_agent.py
```

## Test Categories

### Unit Tests (17 test files)

| File | What It Tests |
|------|-------------|
| `test_agent_routes.py` | Agent chat endpoint, graph invocation, streaming |
| `test_analytics.py` | Analytics pipeline, metric computation |
| `test_analytics_extended.py` | Edge cases in analytics (zero views, missing data) |
| `test_content_engine.py` | Content intelligence pipeline |
| `test_creator_pipeline.py` | Creator profile building, pattern analysis |
| `test_graph_nodes.py` | LangGraph node functions in isolation |
| `test_intelligence.py` | Rule-based extraction: topics, hooks, CTA, sentiment |
| `test_knowledge_health.py` | Knowledge endpoints, hybrid search |
| `test_metrics.py` | `compute_*` metric helpers |
| `test_pipeline.py` | Pipeline stage orchestration, stage runners |
| `test_pipeline_integration.py` | End-to-end pipeline with mocked DB |
| `test_schema_validator.py` | `ContentIntelligenceSchema` validation |
| `test_security.py` | Auth, JWT, password hashing, rate limiting |
| `test_selector.py` | Modality selector: speech/text/visual scores |
| `test_api.py` | Full HTTP API integration (skipped in CI — requires external services) |
| `test_ocr.py` | OCR extraction (skipped in CI — requires video download) |
| `test_clip.py` | CLIP embedding extraction (skipped in CI — requires PyTorch) |
| `test_transcription.py` | Whisper transcription (skipped in CI — requires model download) |

### CI Test Exclusions

Tests excluded from CI (marked as `skipped` or explicitly ignored) are those requiring:
- External API calls (Hiker, OpenAI)
- Large ML model downloads (Whisper, CLIP, EasyOCR)
- Video file downloads
- GPU or significant compute resources

These should be run locally or on a dedicated test runner.

### Test DB Setup

```yaml
# CI: pgvector service container
services:
  postgres:
    image: pgvector/pgvector:pg17
    env:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: vids_clone
    ports:
      - 5432:5432
    options: >-
      --health-cmd pg_isready
      --health-interval 5s
      --health-timeout 5s
      --health-retries 5
```

### Required Env Vars

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vids_clone
JWT_SECRET=test-secret-for-ci
ADMIN_PASSWORD_HASH=test-hash
HIKER_API_TOKEN=test-token
```

## Load Testing

`tests/load/test_agent.py` — simulates concurrent agent chat requests:

```bash
# Configure target URL and run
python tests/load/test_agent.py
```

The script:
- Creates test sessions
- Sends concurrent agent queries
- Measures response times
- Reports throughput (req/s) and error rate

## Coverage Targets

| Category | Target |
|----------|--------|
| Core logic (intelligence, metrics, reranker) | ≥ 95% |
| Routes (API endpoints) | ≥ 85% |
| Graph nodes | ≥ 80% |
| AI/ML (Whisper, OCR, CLIP) | ≥ 60% (compute-bound) |
| Overall | ≥ 80% |

## Testing Conventions

1. **Async tests** use `@pytest.mark.asyncio` and await coroutines
2. **DB-dependent tests** use a real PostgreSQL instance (pgvector)
3. **HTTP tests** can use `respx` to mock external API calls
4. **Test isolation**: each test creates/fetches its own data
5. **Fixtures** in `conftest.py` for DB client, test user, sessions
6. **No network in unit tests** — mock external dependencies
7. **Coverage XML** uploaded to Codecov in CI
