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
