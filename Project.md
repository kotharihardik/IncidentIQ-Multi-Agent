# IncidentIQ — Complete Project Flow

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Infrastructure Boot Sequence](#2-infrastructure-boot-sequence)
3. [Phase 1 — Log Production](#3-phase-1--log-production)
4. [Phase 2 — Kafka Streaming](#4-phase-2--kafka-streaming)
5. [Phase 3 — Three Parallel Consumers](#5-phase-3--three-parallel-consumers)
6. [Phase 4 — Anomaly Detection Gate](#6-phase-4--anomaly-detection-gate)
7. [Phase 5 — Multi-Agent Pipeline (LangGraph)](#7-phase-5--multi-agent-pipeline-langgraph)
8. [Phase 6 — API Layer](#8-phase-6--api-layer)
9. [Complete End-to-End Trace](#9-complete-end-to-end-trace)
10. [Data Shapes at Every Stage](#10-data-shapes-at-every-stage)
11. [What Could Go Wrong and How It's Handled](#11-what-could-go-wrong-and-how-its-handled)

---

## 1. System Overview

IncidentIQ is a fully automated incident response system. From the moment a microservice starts failing, the system collects evidence, detects the anomaly, retrieves similar past incidents, reasons about root cause, generates fixes, and produces a human-readable report — with zero manual intervention.

The system has two modes of operation:

**Streaming mode (production):** Microservice simulators continuously publish logs to Kafka. Three consumers process those logs in parallel. When a consumer detects an anomaly, it fires an incident event that triggers the multi-agent AI pipeline automatically.

**API mode (on-demand):** Any external system can call `POST /incidents/analyze` with a service name and anomaly score to trigger the same pipeline manually.

Both paths run through the same LangGraph workflow and produce the same output.

---

## 2. Infrastructure Boot Sequence

Before any logs flow, the infrastructure must be up. Docker Compose starts services in this dependency order:

```
Zookeeper (2181)
    └── Kafka (9092)
            └── es_consumer
            └── vector_consumer
            └── anomaly_consumer

Elasticsearch (9200)
    └── es_consumer

Qdrant (6333)
    └── vector_consumer

Redis (6379)

Prometheus (9090)
    └── Grafana (3000)

API (8000)
    ├── depends on: Kafka (healthy)
    ├── depends on: Elasticsearch (healthy)
    └── depends on: Qdrant (healthy)
```

Before the API starts accepting traffic, two one-time setup scripts must be run:

```bash
# Create the Elasticsearch 'logs' index with field mappings
python -m infra.elasticsearch_setup

# Create the Qdrant 'incidents' collection with cosine similarity, dim=384
python -m infra.qdrant_setup

# Seed 8 historical incidents into Qdrant for RAG retrieval
python -m infra.seed_historical_incidents
```

The seed script embeds 8 real incident summaries using `all-MiniLM-L6-v2` and stores them in Qdrant. This is what makes RAG retrieval meaningful from day one — without seeds, the vector DB is empty and the LLM gets no historical context.

---

## 3. Phase 1 — Log Production

### Who produces logs

Three simulator files generate structured JSON logs and publish them to Kafka:

- `simulators/payment_service_logs.py` — payments, DB queries, webhook calls
- `simulators/auth_service_logs.py` — JWT validation, session operations
- `simulators/inventory_service_logs.py` — stock checks, Kafka publishes, disk writes

Each simulator calls `kafka/producer.py → publish_log()`, which builds this payload:

```json
{
  "timestamp": "2026-05-20T10:00:00.000000+00:00",
  "service":   "payment-service",
  "level":     "ERROR",
  "message":   "Database connection timeout after 5000ms",
  "trace_id":  "tr-42381",
  "latency_ms": 5000
}
```

The producer uses `acks="all"` and `retries=3` so no log is lost if Kafka is briefly unavailable.

### How to trigger a real incident

The fault injector spikes the error rate on demand:

```bash
python -m simulators.fault_injector --service payment-service --count 80 --rate 0.9
```

This publishes 80 log events to Kafka at 0.1-second intervals, 90% of which are ERROR level. Within ~6 seconds (60 events × 0.1s interval), the sliding window in the anomaly consumer fills up and the detection threshold is crossed.

---

## 4. Phase 2 — Kafka Streaming

All logs land in one topic: `logs-topic`.

The Kafka producer keys each message by service name. This means all logs from `payment-service` go to the same partition in the same order they were produced — critical for the causal chain reconstruction later.

There are two topics in the system:

`logs-topic` — every structured log event from every service. All three consumers read from this topic in their own consumer groups.

`incident-topic` — incident trigger events published by the anomaly consumer when it fires. Contains `incident_id`, `service`, `reason`, `anomaly_score`, and `triggered_at`.

The anomaly consumer publishes to `incident-topic`. The API's `pipeline_service.py` is what actually calls `run_pipeline()` — it does not consume `incident-topic` directly in the current implementation. In a fully async version, a fourth consumer would read from `incident-topic` and call the pipeline. In the current design, the anomaly consumer calls `publish_incident()` to record the event, and the pipeline is triggered either by the API or that consumer directly.

---

## 5. Phase 3 — Three Parallel Consumers

Three consumers run simultaneously as separate Docker services, each in its own consumer group, reading from `logs-topic` independently.

### Consumer 1 — elasticsearch_consumer

**File:** `kafka/consumers/elasticsearch_consumer.py`

**What it does:** Buffers incoming log documents into a list. Every 50 messages, it calls `helpers.bulk()` to index them all into Elasticsearch in one HTTP request. This is more efficient than indexing one document at a time.

**Result:** Every log event is searchable in Elasticsearch within ~1 second of being produced. The `logs` index has field mappings for `timestamp` (date), `service` (keyword), `level` (keyword), and `message` (text with standard analyzer).

### Consumer 2 — vector_consumer

**File:** `kafka/consumers/vector_consumer.py`

**What it does:** Filters to ERROR-level logs only. For each error log, it builds a text string `[service] message`, encodes it with `all-MiniLM-L6-v2` into a 384-dimensional vector, and upserts a `PointStruct` into the Qdrant `incidents` collection.

This is an important design decision: only ERROR logs are embedded, not INFO or WARN. If every log was embedded, the vector DB would be full of noise and semantic retrieval would return irrelevant results.

**Result:** Every unique error pattern that occurs in production gets stored as a semantic vector. Over time, this collection grows into a rich knowledge base of failure signatures.

### Consumer 3 — anomaly_consumer

**File:** `kafka/consumers/anomaly_consumer.py`

**What it does:** Maintains a per-service sliding window of the last 60 log events using `deque(maxlen=60)`. After every new message, it recomputes the error rate for that service. If the error rate exceeds the `ANOMALY_THRESHOLD` (default 0.5, meaning 50% of the last 60 logs are ERRORs) and the service hasn't fired an incident in the last 300 seconds (the cooldown), it calls `publish_incident()`.

The cooldown is critical. Without it, a 5-minute outage generating 3,000 error logs would trigger 3,000 incident events and run the expensive AI pipeline 3,000 times on the same problem.

---

## 6. Phase 4 — Anomaly Detection Gate

This is the decision point between the streaming pipeline and the AI pipeline.

```
New log arrives
    ↓
Append to service window (deque, maxlen=60)
    ↓
Compute error_rate = ERROR_count / window_size
    ↓
score = error_rate
    ↓
Is score >= ANOMALY_THRESHOLD (0.5)?  AND
Is cooldown expired (>300s since last fire)?
    ↓ Yes
Generate incident_id (UUID)
Publish to incident-topic:
  {incident_id, service, reason="high_error_rate", anomaly_score, triggered_at}
Set last_fired[service] = now()
    ↓
AI pipeline triggered
```

The anomaly score in this implementation is simply the error rate. The `.env.example` notes a `RERANKER_MODEL` environment variable which indicates the architecture supports swapping in a cross-encoder reranker — the anomaly score could be replaced by an ML model output (Isolation Forest, LSTM, or similar) without changing any downstream code.

---

## 7. Phase 5 — Multi-Agent Pipeline (LangGraph)

Once an incident is detected, `run_pipeline()` in `agents/workflow.py` is called with the initial state. LangGraph executes six nodes in sequence. Each node receives the full `IncidentState` dict and returns an updated copy.

### The shared state contract

`agents/state.py` defines the `IncidentState` TypedDict — the contract between all agents:

```python
{
  # Inputs
  incident_id, service, reason, anomaly_score, triggered_at,

  # Stage 1 output
  raw_logs: List[dict],

  # Stage 2 output
  error_patterns: List[str],
  causal_chain: List[str],
  error_rate: float,

  # Stage 3 output
  similar_incidents: List[dict],

  # Stage 4 output
  rag_context: str,

  # Stage 5 output
  root_cause: str,
  confidence: float,
  evidence_logs: List[str],

  # Stage 6 output
  fix_recommendations: List[str],

  # Stage 7 output
  report: str
}
```

Every agent reads what it needs and writes its output fields back. Downstream agents never need to know which upstream agent produced a field — they just read from state.

---

### Node 1 — log_retrieval_node

**File:** `agents/log_retrieval.py`

**Input fields used:** `service`, `triggered_at`

**Output fields written:** `raw_logs`

Queries Elasticsearch for all logs from the affected service in a ±5 minute window around `triggered_at`. The query uses a `bool` filter with a `term` on `service.keyword` and a `range` on `timestamp`. Results are sorted ascending by timestamp (oldest first) and capped at 200 documents.

```python
query = {
    "query": {
        "bool": {
            "must": [
                {"term": {"service.keyword": "payment-service"}},
                {"range": {"timestamp": {"gte": "...", "lte": "..."}}}
            ]
        }
    },
    "sort": [{"timestamp": {"order": "asc"}}],
    "size": 200
}
```

**Why ascending sort?** The causal chain must be chronological. If logs are sorted descending, the anomaly classification node would build the causal chain backwards.

---

### Node 2 — anomaly_classification_node

**File:** `agents/anomaly_detection.py`

**Input fields used:** `raw_logs`

**Output fields written:** `error_patterns`, `causal_chain`, `error_rate`

Filters `raw_logs` to ERROR level only. For each error log, it runs the message through `_classify_message()` which tests against 8 regex patterns:

```
"connection.*(timeout|refused|reset)"  →  "DB connection failure"
"(pool|max.?connections|too many)"     →  "Connection pool exhausted"
"out.?of.?memory|OOM|heap"            →  "Memory exhaustion"
"(5\d{2}|internal server error)"       →  "HTTP 5xx error"
"(timeout|timed.?out)"                 →  "Request timeout"
"(null.?pointer|attribute.?error)"     →  "Application exception"
"(disk|storage|no space)"             →  "Disk space issue"
"(kafka|broker|offset)"               →  "Kafka lag / broker issue"
```

Patterns are counted with a `Counter`. Top 5 by frequency become `error_patterns`.

The causal chain is built by walking error logs chronologically and appending the first occurrence of each pattern label:

```
[2026-05-20T10:00:02] DB connection failure: Database connection timeout after 5000ms
[2026-05-20T10:00:04] Connection pool exhausted: Connection pool exhausted: max=5 active=5
[2026-05-20T10:00:07] HTTP 5xx error: Payment gateway returned 503
```

`error_rate` is computed as `len(error_logs) / len(raw_logs)`.

---

### Node 3 — rag_context_node

**File:** `agents/rag_context.py`

**Input fields used:** `service`, `error_patterns`, `causal_chain`, `anomaly_score`, `error_rate`

**Output fields written:** `similar_incidents`, `rag_context`

Builds a compact query string from the top 3 causal chain steps and the error patterns:

```
Service: payment-service. Errors: DB connection failure, Connection pool exhausted.
Chain: DB connection failure: ... → Connection pool exhausted: ...
```

Encodes this with `all-MiniLM-L6-v2` into a 384-dim vector. Queries Qdrant for the top 5 most similar historical incidents by cosine similarity.

Assembles the full RAG context string that will be injected into the LLM prompt:

```
=== Current Incident ===
Service      : payment-service
Anomaly score: 0.87
Error rate   : 0.85
Patterns     : DB connection failure, Connection pool exhausted

=== Causal Chain (chronological) ===
  [2026-05-20T10:00:02] DB connection failure: ...
  [2026-05-20T10:00:04] Connection pool exhausted: ...

=== Similar Past Incidents (ranked by similarity) ===
[1] Score 0.9421
    Summary   : payment-service: DB connection pool exhausted under traffic spike
    Root cause: Connection pool size too small (default 5) for peak load of 300 RPS
    Fix       : Increase SQLALCHEMY_POOL_SIZE to 20; add Redis cache for read queries
```

This is the RAG pattern: retrieve real historical context, inject it into the prompt, so the LLM reasons over facts rather than hallucinating.

---

### Node 4 — root_cause_node

**File:** `agents/root_cause.py`

**Input fields used:** `rag_context`

**Output fields written:** `root_cause`, `confidence`, `evidence_logs`

Sends the full `rag_context` string to the OpenAI API with `temperature=0.0` (deterministic output) and a strict system prompt instructing the model to respond only with a JSON object:

```json
{
  "root_cause": "Connection pool exhausted due to traffic spike exceeding pool capacity of 5",
  "confidence": 0.91,
  "evidence_logs": [
    "[2026-05-20T10:00:04] Connection pool exhausted: Connection pool exhausted: max=5 active=5"
  ]
}
```

`temperature=0.0` is important here. RCA is not creative work — you want the most likely single answer, not variation.

**Fallback:** If the OpenAI call fails (network error, rate limit, invalid JSON response), the node falls back to `"Suspected: {top_error_pattern}"` with `confidence=0.3`. The pipeline continues with degraded quality rather than crashing.

---

### Node 5 — fix_recommendation_node

**File:** `agents/fix_recommendation.py`

**Input fields used:** `root_cause`, `similar_incidents`

**Output fields written:** `fix_recommendations`

Builds a prompt with the root cause and the fix examples from similar incidents retrieved in Node 3:

```
Root cause: Connection pool exhausted due to traffic spike exceeding pool capacity of 5

Historical fixes from similar incidents:
- Increase SQLALCHEMY_POOL_SIZE to 20; add Redis cache for read queries
- Add tenacity retry with exponential backoff and a circuit breaker pattern
```

Sends to OpenAI with `temperature=0.2` (slightly creative — fixes can have valid variations) and a system prompt requiring a JSON array of max 6 steps with immediate mitigations first.

**Fallback:** A `_KNOWN_FIXES` dict maps canonical error pattern names to pre-written fix steps. If the LLM fails, the node checks whether the root cause string contains a known pattern name and returns the corresponding canned steps.

---

### Node 6 — report_generation_node

**File:** `agents/report_generation.py`

**Input fields used:** All fields

**Output fields written:** `report`

No LLM call. Pure Python string formatting. Assembles a structured Markdown incident report from every field in state:

```markdown
# Incident Report — payment-service

**Incident ID**  : a3f2c1d0-...
**Triggered At** : 2026-05-20T10:00:01+00:00
**Report At**    : 2026-05-20 10:02:34 UTC
**Anomaly Score**: 0.87

---

## Affected Service
`payment-service`

## Error Summary
- **Error rate in window** : 85.0%
- **Top error patterns**   : DB connection failure, Connection pool exhausted

## Causal Chain
- [2026-05-20T10:00:02] DB connection failure: ...
- [2026-05-20T10:00:04] Connection pool exhausted: ...

---

## Root Cause Analysis
**Root Cause** : Connection pool exhausted due to traffic spike
**Confidence** : 91%

### Supporting Evidence
  - [2026-05-20T10:00:04] Connection pool exhausted: max=5 active=5

---

## Similar Historical Incidents
  1. [0.9421] payment-service: DB connection pool exhausted under traffic spike

---

## Recommended Actions
1. Increase DB pool size (e.g. SQLALCHEMY_POOL_SIZE=20).
2. Enable connection timeout + recycling (POOL_RECYCLE=300).
3. Add Redis caching layer to reduce DB query volume.
4. Identify and fix slow queries causing long-held connections.

---

*Report generated automatically by IncidentIQ Multi-Agent System*
```

This node is intentionally deterministic. Report formatting should never vary based on LLM temperature.

---

## 8. Phase 6 — API Layer

### FastAPI application (`api/main.py`)

Single FastAPI app with CORS middleware enabled (allowing all origins). Exposes two routes via `api/routers/incidents.py`:

**`POST /incidents/analyze`**

Accepts an `IncidentTrigger` body:

```json
{
  "service": "payment-service",
  "reason": "high_error_rate",
  "anomaly_score": 0.72,
  "triggered_at": "2026-05-20T10:00:01+00:00"
}
```

`triggered_at` is optional — defaults to now if omitted.

Calls `api/services/pipeline_service.py → analyze_incident()` which:
1. Generates a UUID for `incident_id`
2. Builds the initial `IncidentState` dict with all fields set to empty defaults
3. Calls `run_pipeline(initial_state)` — this blocks until all 6 LangGraph nodes complete
4. Returns an `IncidentResponse` with the final state

Returns:

```json
{
  "incident_id": "a3f2c1d0-...",
  "service": "payment-service",
  "root_cause": "Connection pool exhausted due to traffic spike",
  "confidence": 0.91,
  "error_rate": 0.85,
  "error_patterns": ["DB connection failure", "Connection pool exhausted"],
  "fix_recommendations": ["Increase DB pool size...", "Enable connection timeout..."],
  "report": "# Incident Report — payment-service\n...",
  "triggered_at": "2026-05-20T10:00:01+00:00",
  "completed_at": "2026-05-20T10:02:34+00:00"
}
```

**`GET /incidents/logs`**

Query params: `service`, `level`, `start_time`, `end_time`, `size` (1–500, default 50).

Constructs an Elasticsearch `bool` query from whichever params are provided, runs it, and returns the raw log documents sorted by timestamp descending.

**`GET /health`**

Returns `{"status": "ok"}`. Used by Kubernetes liveness and readiness probes.

---

## 9. Complete End-to-End Trace

This traces a single incident from the fault injector to the final report.

```
T+0.0s   fault_injector starts
         → publishes 60 logs to Kafka, 85% ERROR rate
         → each log: {"service":"payment-service","level":"ERROR","message":"Database connection timeout..."}

T+0.1s   Kafka receives first message on logs-topic
         → 3 consumers pick it up simultaneously

T+0.2s   elasticsearch_consumer buffers log #1

T+0.2s   vector_consumer sees ERROR level → encodes with MiniLM → upserts to Qdrant

T+0.2s   anomaly_consumer appends to window for payment-service
         window=[1 log], error_rate=1.0
         score=1.0 >= threshold=0.5 BUT window too small (1/60), edge case handled

T+6.0s   60 logs published (window now full)
         anomaly_consumer: error_rate = 51/60 = 0.85
         score=0.85 >= 0.5, cooldown not active → FIRE

         publish_incident({
           incident_id: "a3f2c1d0-...",
           service: "payment-service",
           reason: "high_error_rate",
           anomaly_score: 0.85,
           triggered_at: "2026-05-20T10:00:06Z"
         })
         last_fired["payment-service"] = now()

T+6.0s   elasticsearch_consumer has buffered 50 logs → bulk flush to ES
         50 documents indexed in one request

T+6.1s   API called (or anomaly_consumer triggers pipeline directly)
         pipeline_service.analyze_incident() called

T+6.1s   LangGraph Node 1 — log_retrieval_node
         ES query: service=payment-service, time window ±5 min around T+0
         → returns 60 log documents sorted ascending

T+6.2s   LangGraph Node 2 — anomaly_classification_node
         51 ERROR logs classified:
           "DB connection failure"      → 18 occurrences
           "Connection pool exhausted"  → 15 occurrences
           "HTTP 5xx error"             → 12 occurrences
           "Request timeout"            →  6 occurrences
         error_rate = 51/60 = 0.85
         causal_chain = [first occurrence of each pattern in timestamp order]

T+6.3s   LangGraph Node 3 — rag_context_node
         query_text = "Service: payment-service. Errors: DB connection failure, Connection pool exhausted..."
         MiniLM encode → 384-dim vector
         Qdrant search top-5 → returns:
           [0.9421] payment-service: DB connection pool exhausted under traffic spike
           [0.8834] order-service: Request timeout cascading from payment-service failure
         rag_context assembled (current incident + causal chain + similar incidents)

T+6.5s   LangGraph Node 4 — root_cause_node
         OpenAI gpt-4o-mini called, temperature=0.0
         Prompt: system_prompt + rag_context
         Response parsed:
           root_cause = "Connection pool exhausted due to traffic spike exceeding capacity of 5"
           confidence = 0.91
           evidence_logs = ["[...] Connection pool exhausted: max=5 active=5"]

T+7.8s   LangGraph Node 5 — fix_recommendation_node
         OpenAI gpt-4o-mini called, temperature=0.2
         Prompt: root_cause + historical fixes from similar incidents
         Response:
           ["Increase DB pool size (SQLALCHEMY_POOL_SIZE=20).",
            "Enable connection timeout + recycling (POOL_RECYCLE=300).",
            "Add Redis caching layer to reduce DB query volume.",
            "Identify and fix slow queries causing long-held connections."]

T+8.9s   LangGraph Node 6 — report_generation_node
         No LLM call. Python string template renders full Markdown report.

T+8.9s   run_pipeline() returns final IncidentState

T+8.9s   analyze_incident() builds IncidentResponse and returns to API caller

T+8.9s   POST /incidents/analyze → 200 OK with full JSON response including report
```

Total time from fault injection to final report: **~9 seconds**, dominated by two OpenAI API calls (~1.3s each).

---

## 10. Data Shapes at Every Stage

### After Node 1 (log_retrieval)
```python
state["raw_logs"] = [
  {"timestamp": "2026-05-20T10:00:01Z", "service": "payment-service",
   "level": "ERROR", "message": "Database connection timeout after 5000ms",
   "trace_id": "tr-42381"},
  # ... up to 200 logs
]
```

### After Node 2 (anomaly_classification)
```python
state["error_patterns"] = ["DB connection failure", "Connection pool exhausted", "HTTP 5xx error"]
state["causal_chain"]   = [
  "[2026-05-20T10:00:01Z] DB connection failure: Database connection timeout after 5000ms",
  "[2026-05-20T10:00:03Z] Connection pool exhausted: Connection pool exhausted: max=5 active=5",
]
state["error_rate"] = 0.85
```

### After Node 3 (rag_context)
```python
state["similar_incidents"] = [
  {"summary": "payment-service: DB connection pool exhausted...",
   "root_cause": "Connection pool size too small (default 5)...",
   "fix": "Increase SQLALCHEMY_POOL_SIZE to 20...",
   "score": 0.9421},
]
state["rag_context"] = "=== Current Incident ===\nService: payment-service\n..."
```

### After Node 4 (root_cause)
```python
state["root_cause"]    = "Connection pool exhausted due to traffic spike exceeding pool capacity of 5"
state["confidence"]    = 0.91
state["evidence_logs"] = ["[2026-05-20T10:00:03Z] Connection pool exhausted: max=5 active=5"]
```

### After Node 5 (fix_recommendation)
```python
state["fix_recommendations"] = [
  "Increase DB pool size (e.g. SQLALCHEMY_POOL_SIZE=20).",
  "Enable connection timeout + recycling (POOL_RECYCLE=300).",
  "Add Redis caching layer to reduce DB query volume.",
  "Identify and fix slow queries causing long-held connections.",
]
```

### After Node 6 (report_generation)
```python
state["report"] = "# Incident Report — payment-service\n\n**Incident ID**: ..."
```

---

## 11. What Could Go Wrong and How It's Handled

**Elasticsearch is down when log_retrieval runs**
The node wraps the ES call in try/except. Returns `raw_logs=[]`. Downstream nodes handle empty logs gracefully — Node 2 returns empty patterns and 0.0 error rate. The LLM in Node 4 receives a context with no logs but still tries to reason with whatever is available.

**Qdrant is down when rag_context runs**
The Qdrant query is wrapped in try/except. Returns `similar_incidents=[]`. The LLM in Node 4 receives context with no historical incidents and produces a lower-confidence answer. Node 5 falls back to `_KNOWN_FIXES` since historical fixes are also empty.

**OpenAI API fails (root_cause_node)**
Falls back to `f"Suspected: {top_pattern}"` with `confidence=0.3`. The pipeline continues and produces a degraded but complete report.

**OpenAI returns invalid JSON (root_cause_node)**
`json.loads()` raises, caught by except, same fallback as above.

**OpenAI API fails (fix_recommendation_node)**
Falls back to `_KNOWN_FIXES` dict lookup by pattern name. If root cause doesn't match any known pattern, returns `["Investigate service logs manually.", "Escalate to on-call engineer."]`.

**Duplicate incidents during a long outage**
The `_COOLDOWN_SECONDS = 300` guard in `anomaly_consumer` prevents re-firing the same service within 5 minutes. The `_last_fired` dict tracks the last fire timestamp per service.

**Kafka lag — consumers fall behind during high log volume**
`elasticsearch_consumer` uses bulk indexing (50 docs per request) to handle bursts. `vector_consumer` is the slowest (embedding is CPU-bound) but only processes ERROR logs, so its volume is much lower. `anomaly_consumer` is stateful in memory and processes messages synchronously — if it falls behind, the sliding window may not reflect real-time state. This is the component most likely to need horizontal scaling under sustained high log volume.

---

*IncidentIQ — Multi-Agent Incident Analysis System*
*Flow document covers code as written in the complete implementation.*
