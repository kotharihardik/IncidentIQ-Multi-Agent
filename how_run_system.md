# IncidentIQ — How to Run the Complete System

## Prerequisites

Before starting, make sure these are installed on your machine:

| Tool | Version | Check |
|------|---------|-------|
| Docker Desktop | 24+ | `docker --version` |
| Docker Compose | 2.x | `docker compose version` |
| Python | 3.11+ | `python --version` |
| Git | any | `git --version` |

You also need an **OpenAI API key** (used by the RCA and Fix agents).

Minimum RAM recommended: **8 GB free** (Elasticsearch alone needs 1 GB).

---

## Step 1 — Clone and Enter the Project

```bash
git clone <your-repo-url>
cd IncidentIQ-Multi-Agent
```

Your folder structure should look like this:

```
IncidentIQ-Multi-Agent/
├── agents/
├── api/
├── infra/
├── kafka/
├── k8s/
├── monitoring/
├── simulators/
├── docker-compose.yml
├── .env.example
└── .gitignore
```

---

## Step 2 — Create Your .env File

Copy the example and fill in your OpenAI key:

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder:

```bash
# Change this line:
OPENAI_API_KEY=your-openai-api-key

# To your real key:
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
```

Everything else in `.env` can stay as-is for local development. The defaults
point to `localhost` ports which match the Docker Compose service definitions.

---

## Step 3 — Start All Infrastructure Services

```bash
docker compose up -d
```

This starts 10 containers:

```
zookeeper       → port 2181
kafka           → port 9092
elasticsearch   → port 9200
qdrant          → port 6333
redis           → port 6379
prometheus      → port 9090
grafana         → port 3000
api             → port 8000
es_consumer     → (no external port)
vector_consumer → (no external port)
anomaly_consumer→ (no external port)
```

Wait for all services to be healthy. Check status:

```bash
docker compose ps
```

All services should show `healthy` or `running`. Elasticsearch is the slowest —
it can take 30–60 seconds. Keep checking until it shows `healthy`:

```bash
# Watch status live (updates every 2 seconds)
watch docker compose ps
```

You can also verify each service manually:

```bash
# Kafka
docker compose exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092

# Elasticsearch
curl http://localhost:9200/_cluster/health

# Qdrant
curl http://localhost:6333/healthz

# API
curl http://localhost:8000/health
```

Expected responses:

```
Elasticsearch: {"status":"green",...}
Qdrant:        {"title":"qdrant - vector search engine","version":"1.9.1"}
API:           {"status":"ok"}
```

---

## Step 4 — One-Time Setup (Run Once Per Fresh Install)

These three scripts create the database schema and seed historical data.
They are idempotent — running them twice is safe.

Open a new terminal tab and run from the project root:

```bash
# Install Python dependencies locally (for running setup scripts and simulators)
pip install -r api/requirements.txt

# 1. Create the Elasticsearch 'logs' index with field mappings
python -m infra.elasticsearch_setup

# 2. Create the Qdrant 'incidents' vector collection (384-dim, cosine similarity)
python -m infra.qdrant_setup

# 3. Seed 8 historical incidents into Qdrant for RAG retrieval
python -m infra.seed_historical_incidents
```

Expected output:

```
[elasticsearch_setup] Index 'logs' created.
[qdrant_setup] Collection 'incidents' created (dim=384).
[seed] Inserted 8 historical incidents into 'incidents'.
```

Without Step 4, the RAG agent has no historical context and the LLM will
produce lower-confidence root cause analysis.

---

## Step 5 — Verify Consumers Are Running

The three Kafka consumers started automatically with `docker compose up`.
Verify they are alive and listening:

```bash
docker compose logs es_consumer
docker compose logs vector_consumer
docker compose logs anomaly_consumer
```

Expected output for each:

```
[elasticsearch_consumer] Listening on logs-topic …
[vector_consumer] Listening on logs-topic …
[anomaly_consumer] Listening on logs-topic …
```

If any consumer shows errors, check that Kafka and the target database
(Elasticsearch or Qdrant) are healthy first, then restart the consumer:

```bash
docker compose restart es_consumer
docker compose restart vector_consumer
docker compose restart anomaly_consumer
```

---

## Step 6 — Start the Log Simulators

The simulators generate continuous log traffic. Open a separate terminal for each:

**Terminal A — Payment service (most likely to generate incidents):**

```bash
python -m simulators.payment_service_logs
```

**Terminal B — Auth service:**

```bash
python -m simulators.auth_service_logs
```

**Terminal C — Inventory service:**

```bash
python -m simulators.inventory_service_logs
```

Each simulator prints nothing — it silently publishes to Kafka. You can verify
logs are flowing by watching the Elasticsearch consumer:

```bash
docker compose logs -f es_consumer
```

You should see bulk index confirmations every few seconds:

```
[elasticsearch_consumer] Indexed 50 documents
[elasticsearch_consumer] Indexed 50 documents
```

---

## Step 7 — Trigger a Real Incident

The simulators run at low error rates (3–5%) which won't cross the anomaly
threshold on their own. Use the fault injector to simulate a real failure:

```bash
# Spike payment-service with 85% error rate, 80 log events
python -m simulators.fault_injector --service payment-service --count 80 --rate 0.9
```

Watch what happens in the anomaly consumer:

```bash
docker compose logs -f anomaly_consumer
```

After about 6 seconds you will see:

```
[anomaly_consumer] INCIDENT a3f2c1d0-... | payment-service | score=0.85
```

The anomaly consumer has detected the incident and published it to
`incident-topic`. The AI pipeline is now triggered.

---

## Step 8 — Run the Full AI Pipeline via API

You can trigger the pipeline manually at any time via the REST API.
No fault injection needed — just call the endpoint directly.

**Using curl:**

```bash
curl -X POST http://localhost:8000/incidents/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "service": "payment-service",
    "reason": "high_error_rate",
    "anomaly_score": 0.85
  }'
```

**Using Python:**

```python
import requests

response = requests.post(
    "http://localhost:8000/incidents/analyze",
    json={
        "service": "payment-service",
        "reason": "high_error_rate",
        "anomaly_score": 0.85
    }
)
print(response.json())
```

**Using the Swagger UI (easiest):**

Open your browser: http://localhost:8000/docs

Click `POST /incidents/analyze` → `Try it out` → fill in the body → `Execute`.

The response takes 8–15 seconds (two OpenAI API calls). You will receive:

```json
{
  "incident_id": "a3f2c1d0-...",
  "service": "payment-service",
  "root_cause": "Connection pool exhausted due to traffic spike exceeding capacity of 5",
  "confidence": 0.91,
  "error_rate": 0.85,
  "error_patterns": ["DB connection failure", "Connection pool exhausted"],
  "fix_recommendations": [
    "Increase DB pool size (e.g. SQLALCHEMY_POOL_SIZE=20).",
    "Enable connection timeout + recycling (POOL_RECYCLE=300).",
    "Add Redis caching layer to reduce DB query volume.",
    "Identify and fix slow queries causing long-held connections."
  ],
  "report": "# Incident Report — payment-service\n\n**Incident ID**: ...",
  "triggered_at": "2026-05-20T10:00:01+00:00",
  "completed_at": "2026-05-20T10:00:09+00:00"
}
```

---

## Step 9 — Query Logs

Check what logs are stored in Elasticsearch:

```bash
# All logs (last 50)
curl "http://localhost:8000/incidents/logs"

# Only ERROR logs from payment-service
curl "http://localhost:8000/incidents/logs?service=payment-service&level=ERROR&size=20"

# Logs in a time window
curl "http://localhost:8000/incidents/logs?start_time=2026-05-20T10:00:00Z&end_time=2026-05-20T10:10:00Z"
```

---

## Step 10 — Open Monitoring Dashboards

**Grafana** (metrics dashboard):

```
http://localhost:3000
Username: admin
Password: admin
```

**Prometheus** (raw metrics):

```
http://localhost:9090
```

**Elasticsearch** (direct query):

```
http://localhost:9200/logs/_search?pretty&size=5
```

**Qdrant** (vector DB web UI):

```
http://localhost:6333/dashboard
```

**API Docs (Swagger)**:

```
http://localhost:8000/docs
```

---

## All Services at a Glance

| Service | URL | Purpose |
|---------|-----|---------|
| FastAPI | http://localhost:8000 | Main API |
| Swagger UI | http://localhost:8000/docs | API docs and testing |
| Elasticsearch | http://localhost:9200 | Log search |
| Qdrant | http://localhost:6333 | Vector DB |
| Grafana | http://localhost:3000 | Metrics dashboard |
| Prometheus | http://localhost:9090 | Metrics collector |
| Kafka | localhost:9092 | Log streaming broker |
| Redis | localhost:6379 | Cache |

---

## Useful Commands

**Watch all container logs live:**

```bash
docker compose logs -f
```

**Watch a specific service:**

```bash
docker compose logs -f api
docker compose logs -f anomaly_consumer
```

**Restart a single service:**

```bash
docker compose restart api
```

**Stop everything:**

```bash
docker compose down
```

**Stop and delete all volumes (full reset — loses all indexed logs and vectors):**

```bash
docker compose down -v
```

**Rebuild the application image after code changes:**

```bash
docker compose build api es_consumer vector_consumer anomaly_consumer
docker compose up -d
```

**Check Kafka topics:**

```bash
docker compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list
```

**Read Kafka messages from the beginning:**

```bash
docker compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic logs-topic \
  --from-beginning \
  --max-messages 10
```

**Count logs in Elasticsearch:**

```bash
curl http://localhost:9200/logs/_count
```

**Count vectors in Qdrant:**

```bash
curl http://localhost:6333/collections/incidents
```

---

## Run Without Docker (Local Dev Mode)

If you prefer to run the Python services directly (faster iteration, easier debugging):

**Terminal 1 — Start infrastructure only:**

```bash
docker compose up -d zookeeper kafka elasticsearch qdrant redis prometheus grafana
```

**Terminal 2 — Run setup scripts:**

```bash
pip install -r api/requirements.txt
python -m infra.elasticsearch_setup
python -m infra.qdrant_setup
python -m infra.seed_historical_incidents
```

**Terminal 3 — FastAPI:**

```bash
python -m api.main
```

**Terminal 4 — Elasticsearch consumer:**

```bash
python -m kafka.consumers.elasticsearch_consumer
```

**Terminal 5 — Vector consumer:**

```bash
python -m kafka.consumers.vector_consumer
```

**Terminal 6 — Anomaly consumer:**

```bash
python -m kafka.consumers.anomaly_consumer
```

**Terminal 7 — Simulators:**

```bash
python -m simulators.payment_service_logs
```

**Terminal 8 — Fault injector (when ready to test):**

```bash
python -m simulators.fault_injector --service payment-service --count 80 --rate 0.9
```

---

## Common Errors and Fixes

**`Connection refused` on Kafka at startup**

Kafka takes 20–30 seconds to start after Zookeeper. Wait and retry.

```bash
docker compose restart es_consumer vector_consumer anomaly_consumer
```

**`Elasticsearch index already exists`**

Normal — the setup script is idempotent. You can ignore this message.

**`OpenAI API key invalid`**

Check your `.env` file. Make sure there are no spaces around the `=` sign and the key starts with `sk-`.

**`sentence_transformers` slow on first run**

The MiniLM model (~90 MB) is downloaded on first use. This is a one-time download.

**API returns `500 Internal Server Error`**

Check the API logs:

```bash
docker compose logs api
```

Most common causes: Elasticsearch not yet healthy, missing `.env` file, or OpenAI key not set.

**`docker compose` vs `docker-compose`**

This project uses Docker Compose v2 (`docker compose`). If you have the older
standalone version (`docker-compose`), all commands work the same — just replace
`docker compose` with `docker-compose`.

---

## Quick Start Checklist

```
[ ] Docker Desktop running
[ ] cp .env.example .env  and  set OPENAI_API_KEY
[ ] docker compose up -d
[ ] Wait for all services: healthy
[ ] pip install -r api/requirements.txt
[ ] python -m infra.elasticsearch_setup
[ ] python -m infra.qdrant_setup
[ ] python -m infra.seed_historical_incidents
[ ] docker compose logs es_consumer  →  "Listening on logs-topic"
[ ] python -m simulators.payment_service_logs  (background terminal)
[ ] python -m simulators.fault_injector --service payment-service --count 80 --rate 0.9
[ ] curl -X POST http://localhost:8000/incidents/analyze ...
[ ] View report in response JSON
```