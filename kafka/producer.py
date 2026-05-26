import os
import json
from datetime import datetime, timezone
from kafka import KafkaProducer as _KafkaProducer

_BROKER     = os.getenv("KAFKA_BROKER", "localhost:9092")
_LOGS_TOPIC = "logs-topic"
_INC_TOPIC  = "incident-topic"


def _make_producer() -> _KafkaProducer:
    return _KafkaProducer(
        bootstrap_servers=_BROKER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        acks="all",
        retries=3,
    )


_producer: _KafkaProducer | None = None


def get_producer() -> _KafkaProducer:
    global _producer
    if _producer is None:
        _producer = _make_producer()
    return _producer


def publish_log(
    service: str,
    level: str,
    message: str,
    extra: dict | None = None,
) -> None:
    """
    Publish a structured log event to logs-topic.

    Parameters
    ----------
    service : str   e.g. "payment-service"
    level   : str   INFO | WARN | ERROR
    message : str   human-readable log line
    extra   : dict  optional additional fields merged into the payload
    """
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service":   service,
        "level":     level.upper(),
        "message":   message,
        **(extra or {}),
    }
    get_producer().send(_LOGS_TOPIC, key=service, value=payload)


def publish_incident(
    incident_id: str,
    service: str,
    reason: str,
    anomaly_score: float,
) -> None:
    """
    Publish an incident trigger to incident-topic.
    Consumed by the anomaly_consumer which kicks off the agent pipeline.
    """
    payload = {
        "incident_id":   incident_id,
        "service":       service,
        "reason":        reason,
        "anomaly_score": anomaly_score,
        "triggered_at":  datetime.now(timezone.utc).isoformat(),
    }
    get_producer().send(_INC_TOPIC, key=service, value=payload)
    get_producer().flush()
