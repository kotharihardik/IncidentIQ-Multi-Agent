import os
import json
from kafka import KafkaConsumer
from elasticsearch import Elasticsearch, helpers

_BROKER  = os.getenv("KAFKA_BROKER", "localhost:9092")
_ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
_INDEX   = os.getenv("ES_INDEX", "logs")
_BATCH   = 50  # bulk-index every N messages


def run() -> None:
    consumer = KafkaConsumer(
        "logs-topic",
        bootstrap_servers=_BROKER,
        group_id="elasticsearch-consumer",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    es = Elasticsearch(_ES_HOST)
    buffer: list[dict] = []

    print("[elasticsearch_consumer] Listening on logs-topic …")
    for message in consumer:
        doc = message.value
        buffer.append({
            "_index": _INDEX,
            "_source": doc,
        })

        if len(buffer) >= _BATCH:
            _flush(es, buffer)
            buffer.clear()


def _flush(es: Elasticsearch, buffer: list[dict]) -> None:
    try:
        ok, errors = helpers.bulk(es, buffer, raise_on_error=False)
        if errors:
            print(f"[elasticsearch_consumer] Bulk errors: {errors[:3]}")
        else:
            print(f"[elasticsearch_consumer] Indexed {ok} documents")
    except Exception as exc:
        print(f"[elasticsearch_consumer] Flush error: {exc}")


if __name__ == "__main__":
    run()
