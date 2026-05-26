import os
from elasticsearch import Elasticsearch

_ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
_INDEX   = os.getenv("ES_INDEX", "logs")

_MAPPING = {
    "mappings": {
        "properties": {
            "timestamp": {"type": "date"},
            "service":   {"type": "keyword"},
            "level":     {"type": "keyword"},
            "message":   {"type": "text",    "analyzer": "standard"},
            "trace_id":  {"type": "keyword"},
            "user_id":   {"type": "keyword"},
            "latency_ms":{"type": "integer"},
            "status_code":{"type": "integer"},
        }
    },
    "settings": {
        "number_of_shards":   1,
        "number_of_replicas": 0,
        "refresh_interval":   "1s",
    }
}


def setup() -> None:
    es = Elasticsearch(_ES_HOST)
    if es.indices.exists(index=_INDEX):
        print(f"[elasticsearch_setup] Index '{_INDEX}' already exists — skipping.")
        return
    es.indices.create(index=_INDEX, body=_MAPPING)
    print(f"[elasticsearch_setup] Index '{_INDEX}' created.")


if __name__ == "__main__":
    setup()
