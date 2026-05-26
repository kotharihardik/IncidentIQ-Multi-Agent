import os
import json
import uuid
from kafka import KafkaConsumer
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

_BROKER     = os.getenv("KAFKA_BROKER", "localhost:9092")
_QDRANT     = os.getenv("QDRANT_HOST", "http://localhost:6333")
_COLLECTION = os.getenv("QDRANT_COLLECTION", "incidents")
_EMB_MODEL  = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_ONLY_ERRORS = True   # only embed ERROR-level logs to keep vector DB focused


def run() -> None:
    model    = SentenceTransformer(_EMB_MODEL)
    qdrant   = QdrantClient(url=_QDRANT)
    consumer = KafkaConsumer(
        "logs-topic",
        bootstrap_servers=_BROKER,
        group_id="vector-consumer",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    print("[vector_consumer] Listening on logs-topic …")
    for message in consumer:
        doc = message.value
        if _ONLY_ERRORS and doc.get("level", "").upper() != "ERROR":
            continue

        text = f"[{doc.get('service','')}] {doc.get('message','')}"
        vector = model.encode(text).tolist()

        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "summary":    text[:200],
                "service":    doc.get("service", ""),
                "timestamp":  doc.get("timestamp", ""),
                "root_cause": "",   # filled later by RCA agent feedback loop
                "fix":        "",
            },
        )
        try:
            qdrant.upsert(collection_name=_COLLECTION, points=[point])
        except Exception as exc:
            print(f"[vector_consumer] Qdrant upsert error: {exc}")


if __name__ == "__main__":
    run()
