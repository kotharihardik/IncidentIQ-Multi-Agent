<<<<<<< HEAD
import os
import uuid
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

_QDRANT     = os.getenv("QDRANT_HOST", "http://localhost:6333")
_COLLECTION = os.getenv("QDRANT_COLLECTION", "incidents")
_EMB_MODEL  = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

HISTORICAL_INCIDENTS = [
    {
        "summary":    "payment-service: DB connection pool exhausted under traffic spike",
        "root_cause": "Connection pool size too small (default 5) for peak load of 300 RPS",
        "fix":        "Increase SQLALCHEMY_POOL_SIZE to 20; add Redis cache for read queries",
    },
    {
        "summary":    "order-service: Request timeout cascading from payment-service failure",
        "root_cause": "No circuit breaker; payment-service degradation caused order threads to hang",
        "fix":        "Add tenacity retry with exponential backoff and a circuit breaker pattern",
    },
    {
        "summary":    "auth-service: JWT validation latency spike causing login failures",
        "root_cause": "RSA key decoding on every request due to missing in-memory key cache",
        "fix":        "Cache the decoded RSA public key at startup; add Redis token blacklist",
    },
    {
        "summary":    "payment-service: OOM kill after memory leak in webhook processor",
        "root_cause": "Unclosed HTTP sessions accumulating in long-running webhook loop",
        "fix":        "Use async context manager (async with aiohttp.ClientSession()) in webhook handler",
    },
    {
        "summary":    "order-service: Kafka consumer lag spike causing delayed order confirmations",
        "root_cause": "Single consumer partition with blocking DB write per message",
        "fix":        "Increase consumer group replicas to 3; batch DB writes with bulk insert",
    },
    {
        "summary":    "inventory-service: Disk full causing write failures",
        "root_cause": "Log rotation not configured; 30 days of unrotated debug logs filled disk",
        "fix":        "Configure logrotate with 7-day retention; add disk usage alert at 80%",
    },
    {
        "summary":    "payment-service: High 5xx rate after deployment due to missing env variable",
        "root_cause": "New release required PAYMENT_GATEWAY_SECRET not present in k8s configmap",
        "fix":        "Add config validation at startup; update deployment checklist",
    },
    {
        "summary":    "auth-service: Brute-force login attempts causing high CPU",
        "root_cause": "No rate limiting on /login endpoint; bcrypt cost factor 12 under load",
        "fix":        "Add IP-based rate limiting (max 10/min); lower bcrypt cost to 10 behind rate limit",
    },
]


def seed() -> None:
    model  = SentenceTransformer(_EMB_MODEL)
    client = QdrantClient(url=_QDRANT)
    points = []

    for incident in HISTORICAL_INCIDENTS:
        text   = incident["summary"]
        vector = model.encode(text).tolist()
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload=incident,
        ))

    client.upsert(collection_name=_COLLECTION, points=points)
    print(f"[seed] Inserted {len(points)} historical incidents into '{_COLLECTION}'.")


if __name__ == "__main__":
    seed()
=======
"""Seed Qdrant with historical incidents for the RAG agent.

Run this after qdrant_setup.py so the collection exists.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer


load_dotenv()

QDRANT_HOST = os.getenv("QDRANT_HOST", "http://localhost:6333")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "incidents")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


HISTORICAL_INCIDENTS: list[dict[str, Any]] = [
	{
		"incident_id": "hist_001",
		"service": "payment-service",
		"description": "Payment API started timing out when the checkout flow retried the same order three times.",
		"root_cause": "PostgreSQL connection pool exhaustion caused checkout workers to queue behind stalled transactions.",
		"fix": "Increase the DB pool size, add request idempotency, and reduce retry fan-out in the checkout worker.",
		"severity": "critical",
		"observed_at": "2024-01-15T10:12:00Z",
	},
	{
		"incident_id": "hist_002",
		"service": "auth-service",
		"description": "JWT verification failures spiked after a key rotation in the identity provider.",
		"root_cause": "The auth service had not refreshed the JWKS cache after the signing key changed.",
		"fix": "Clear the JWKS cache, shorten cache TTL, and add a key rotation health check.",
		"severity": "critical",
		"observed_at": "2024-01-19T08:41:00Z",
	},
	{
		"incident_id": "hist_003",
		"service": "payment-service",
		"description": "Stripe webhook delivery lag caused duplicate payment confirmation events.",
		"root_cause": "Webhook consumers lacked idempotency keys and processed the same event multiple times.",
		"fix": "Persist webhook event ids, reject duplicates, and retry only on transient gateway errors.",
		"severity": "high",
		"observed_at": "2024-01-24T14:05:00Z",
	},
	{
		"incident_id": "hist_004",
		"service": "inventory-service",
		"description": "Bulk indexing to Elasticsearch slowed inventory search and delayed product updates.",
		"root_cause": "A mapping conflict forced Elasticsearch to reject part of the bulk load.",
		"fix": "Align field mappings, reindex the catalog, and batch writes into smaller payloads.",
		"severity": "high",
		"observed_at": "2024-02-02T16:18:00Z",
	},
	{
		"incident_id": "hist_005",
		"service": "auth-service",
		"description": "Users were locked out after repeated login attempts from a small range of IPs.",
		"root_cause": "The account lockout threshold was too aggressive for normal mobile network retries.",
		"fix": "Relax the lockout policy, add IP reputation checks, and separate user and bot throttles.",
		"severity": "critical",
		"observed_at": "2024-02-08T09:32:00Z",
	},
	{
		"incident_id": "hist_006",
		"service": "payment-service",
		"description": "Refund requests piled up while the orders table showed increasing deadlocks.",
		"root_cause": "A missing index caused refund workers to scan and lock the same order rows.",
		"fix": "Add the missing index, shorten transaction scope, and serialize refund state updates.",
		"severity": "critical",
		"observed_at": "2024-02-13T11:47:00Z",
	},
	{
		"incident_id": "hist_007",
		"service": "inventory-service",
		"description": "Product quantity briefly went negative during a flash sale.",
		"root_cause": "Two parallel reservation requests updated the same stock row without atomic checks.",
		"fix": "Use a compare-and-swap update, add a reservation ledger, and block oversells at write time.",
		"severity": "high",
		"observed_at": "2024-02-19T13:10:00Z",
	},
	{
		"incident_id": "hist_008",
		"service": "auth-service",
		"description": "OAuth login returned state mismatch errors for a subset of browsers.",
		"root_cause": "The state token was lost when the browser switched from the login domain to the callback domain.",
		"fix": "Store the state token in a shared session store and verify callback domain configuration.",
		"severity": "medium",
		"observed_at": "2024-02-26T07:55:00Z",
	},
	{
		"incident_id": "hist_009",
		"service": "payment-service",
		"description": "Slow payment retries created a queue backlog and delayed checkout completion.",
		"root_cause": "The retry policy hammered the same downstream gateway during a partial outage.",
		"fix": "Add exponential backoff, cap retries, and circuit-break the payment gateway path.",
		"severity": "high",
		"observed_at": "2024-03-03T15:21:00Z",
	},
	{
		"incident_id": "hist_010",
		"service": "inventory-service",
		"description": "Low stock alerts were delayed even though the warehouse feed was healthy.",
		"root_cause": "The cache TTL was too long, so the stock page kept stale values.",
		"fix": "Shorten the TTL, invalidate on warehouse updates, and emit cache metrics.",
		"severity": "medium",
		"observed_at": "2024-03-08T10:03:00Z",
	},
	{
		"incident_id": "hist_011",
		"service": "payment-service",
		"description": "Card tokenization failed after the upstream gateway returned repeated 502s.",
		"root_cause": "A certificate mismatch broke the TLS handshake to the tokenization endpoint.",
		"fix": "Refresh certificates, add TLS expiry alerts, and fall back to a secondary route.",
		"severity": "critical",
		"observed_at": "2024-03-13T12:29:00Z",
	},
	{
		"incident_id": "hist_012",
		"service": "auth-service",
		"description": "Session validation errors increased after a rolling deploy of the auth service.",
		"root_cause": "Clock skew between nodes invalidated short-lived session tokens.",
		"fix": "Synchronize NTP, raise token skew tolerance slightly, and alert on drift.",
		"severity": "medium",
		"observed_at": "2024-03-18T08:14:00Z",
	},
	{
		"incident_id": "hist_013",
		"service": "inventory-service",
		"description": "Kafka consumer rebalance events paused stock sync for several minutes.",
		"root_cause": "Consumer sessions were too short and triggered repeated group rebalances.",
		"fix": "Increase session timeout, tune max poll interval, and smooth rebalance handling.",
		"severity": "high",
		"observed_at": "2024-03-22T16:43:00Z",
	},
	{
		"incident_id": "hist_014",
		"service": "payment-service",
		"description": "Duplicate transaction ids appeared when the payment queue was retried manually.",
		"root_cause": "The idempotency key was not persisted before sending the provider request.",
		"fix": "Persist idempotency keys first and reject repeated transaction ids at the API boundary.",
		"severity": "high",
		"observed_at": "2024-03-29T09:50:00Z",
	},
	{
		"incident_id": "hist_015",
		"service": "auth-service",
		"description": "Password reset emails were generated but the user verification step failed.",
		"root_cause": "The email verification token expired before the callback request completed.",
		"fix": "Extend token TTL slightly, reduce callback latency, and log the end-to-end reset duration.",
		"severity": "medium",
		"observed_at": "2024-04-04T11:08:00Z",
	},
	{
		"incident_id": "hist_016",
		"service": "payment-service",
		"description": "Checkout latency increased after the payment worker crashed mid-batch.",
		"root_cause": "The worker container ran out of memory while serializing large retry payloads.",
		"fix": "Cap payload size, add memory limits, and split retries into smaller chunks.",
		"severity": "high",
		"observed_at": "2024-04-09T18:25:00Z",
	},
	{
		"incident_id": "hist_017",
		"service": "inventory-service",
		"description": "Search results degraded because Elasticsearch shards were relocating during peak traffic.",
		"root_cause": "Shard relocation starved query threads and increased read latency.",
		"fix": "Pause heavy relocations during peak hours and rebalance shards during low traffic.",
		"severity": "medium",
		"observed_at": "2024-04-15T13:36:00Z",
	},
	{
		"incident_id": "hist_018",
		"service": "auth-service",
		"description": "Single sign-on metadata fetches failed with intermittent DNS resolution errors.",
		"root_cause": "The metadata endpoint rotated addresses before the DNS cache refreshed.",
		"fix": "Shorten DNS cache TTL and add a backup fetch path for identity metadata.",
		"severity": "high",
		"observed_at": "2024-04-21T06:41:00Z",
	},
	{
		"incident_id": "hist_019",
		"service": "payment-service",
		"description": "Gateway calls returned 504s during a short traffic spike.",
		"root_cause": "The upstream payment provider exceeded its timeout budget and dropped slow requests.",
		"fix": "Increase timeout visibility, add circuit breaking, and route retries to a fallback provider.",
		"severity": "high",
		"observed_at": "2024-04-28T14:57:00Z",
	},
	{
		"incident_id": "hist_020",
		"service": "inventory-service",
		"description": "Stock reconciliation lagged after a schema change in the warehouse feed.",
		"root_cause": "The consumer parser still expected the old payload shape.",
		"fix": "Deploy the parser update first, version the payload, and add schema compatibility tests.",
		"severity": "high",
		"observed_at": "2024-05-03T10:15:00Z",
	},
	{
		"incident_id": "hist_021",
		"service": "payment-service",
		"description": "Refund confirmation events were sent twice after a manual replay job.",
		"root_cause": "The replay job reused old messages without marking the original ids as processed.",
		"fix": "Mark replayed messages explicitly, store processed ids, and make the replay idempotent.",
		"severity": "high",
		"observed_at": "2024-05-09T17:12:00Z",
	},
	{
		"incident_id": "hist_022",
		"service": "auth-service",
		"description": "MFA challenge creation failed for users whose devices were behind a restrictive proxy.",
		"root_cause": "The challenge endpoint timed out before the proxy completed the handshake.",
		"fix": "Raise the handshake timeout, add proxy-friendly retries, and log MFA challenge latency.",
		"severity": "critical",
		"observed_at": "2024-05-14T09:03:00Z",
	},
	{
		"incident_id": "hist_023",
		"service": "inventory-service",
		"description": "Category pages loaded stale product counts after a warehouse sync pause.",
		"root_cause": "The cache invalidation path failed when the sync service restarted.",
		"fix": "Persist invalidation events, add restart-safe consumers, and shorten stale cache windows.",
		"severity": "medium",
		"observed_at": "2024-05-20T12:44:00Z",
	},
	{
		"incident_id": "hist_024",
		"service": "payment-service",
		"description": "Currency conversion values drifted after a rate provider outage.",
		"root_cause": "The service kept using a stale cached exchange rate beyond its safe TTL.",
		"fix": "Expire cached rates sooner, add provider failover, and alert on stale currency data.",
		"severity": "high",
		"observed_at": "2024-05-27T15:18:00Z",
	},
	{
		"incident_id": "hist_025",
		"service": "auth-service",
		"description": "A burst of failed logins made the login endpoint appear slower than normal.",
		"root_cause": "The rate limiter shared counters across too many users and introduced contention.",
		"fix": "Shard the limiter keys, lower the lock contention, and separate auth error counters from login counters.",
		"severity": "medium",
		"observed_at": "2024-06-02T08:27:00Z",
	},
]


def _build_embedding_text(incident: dict[str, Any]) -> str:
	return (
		f"Service: {incident['service']}\n"
		f"Severity: {incident['severity']}\n"
		f"Description: {incident['description']}\n"
		f"Root cause: {incident['root_cause']}\n"
		f"Fix: {incident['fix']}"
	)


def _ensure_collection_exists(client: QdrantClient) -> None:
	existing_collections = {collection.name for collection in client.get_collections().collections}
	if COLLECTION_NAME not in existing_collections:
		raise RuntimeError(
			f"Collection '{COLLECTION_NAME}' does not exist. Run infra/qdrant_setup.py first."
		)


def seed_incidents() -> None:
	"""Embed and store the historical incidents in Qdrant."""

	client = QdrantClient(url=QDRANT_HOST)
	_ensure_collection_exists(client)

	model = SentenceTransformer(EMBEDDING_MODEL)
	embed_texts = [_build_embedding_text(incident) for incident in HISTORICAL_INCIDENTS]
	embeddings = model.encode(embed_texts, convert_to_numpy=True, normalize_embeddings=True)

	points = []
	for index, incident in enumerate(HISTORICAL_INCIDENTS, start=1):
		payload = dict(incident)
		payload["embedding_text"] = embed_texts[index - 1]
		point = PointStruct(
			id=index,
			vector=embeddings[index - 1].tolist(),
			payload=payload,
		)
		points.append(point)

	client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
	print(f"Seeded {len(points)} historical incidents into Qdrant collection '{COLLECTION_NAME}'.")


if __name__ == "__main__":
	seed_incidents()
>>>>>>> d8fc6125ea1b55e2ebb060d35dc138d94da32ffd
