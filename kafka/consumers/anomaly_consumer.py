import os
import json
import uuid
import time
from collections import deque, defaultdict
from datetime import datetime, timezone
from kafka import KafkaConsumer

from kafka.producer import publish_incident

_BROKER            = os.getenv("KAFKA_BROKER", "localhost:9092")
_THRESHOLD         = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))
_WINDOW_SIZE       = 60       # last N log events per service
_COOLDOWN_SECONDS  = 300      # don't re-fire the same service within 5 min
_MIN_ERROR_RATE    = 0.30     # rule-based: fire if >30% errors in window


# Per-service sliding window and last-fire timestamp
_windows: dict[str, deque]  = defaultdict(lambda: deque(maxlen=_WINDOW_SIZE))
_last_fired: dict[str, float] = {}


def _error_rate(window: deque) -> float:
    if not window:
        return 0.0
    errors = sum(1 for l in window if l.get("level", "").upper() == "ERROR")
    return errors / len(window)


def _should_fire(service: str, score: float) -> bool:
    now = time.time()
    last = _last_fired.get(service, 0)
    if now - last < _COOLDOWN_SECONDS:
        return False
    return score >= _THRESHOLD


def run() -> None:
    consumer = KafkaConsumer(
        "logs-topic",
        bootstrap_servers=_BROKER,
        group_id="anomaly-consumer",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )

    print("[anomaly_consumer] Listening on logs-topic …")
    for message in consumer:
        doc = message.value
        service = doc.get("service", "unknown")
        _windows[service].append(doc)

        rate = _error_rate(_windows[service])

        # Anomaly score = error rate (you can swap in an ML model here)
        score = round(rate, 4)

        if _should_fire(service, score):
            incident_id = str(uuid.uuid4())
            print(f"[anomaly_consumer] INCIDENT {incident_id} | {service} | score={score}")
            publish_incident(
                incident_id=incident_id,
                service=service,
                reason="high_error_rate",
                anomaly_score=score,
            )
            _last_fired[service] = time.time()


if __name__ == "__main__":
    run()
