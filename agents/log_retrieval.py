import os
from datetime import datetime, timedelta, timezone
from elasticsearch import Elasticsearch

from agents.state import IncidentState

_es = Elasticsearch(os.getenv("ES_HOST", "http://localhost:9200"))
_INDEX = os.getenv("ES_INDEX", "logs")
_WINDOW_MINUTES = int(os.getenv("LOG_WINDOW_MINUTES", "5"))
_MAX_LOGS = int(os.getenv("LOG_MAX_FETCH", "200"))


def log_retrieval_node(state: IncidentState) -> IncidentState:
    """
    Fetch logs from Elasticsearch in a ±WINDOW_MINUTES window around the
    incident trigger time, filtered to the affected service.
    """
    triggered_at = datetime.fromisoformat(state["triggered_at"])
    start = (triggered_at - timedelta(minutes=_WINDOW_MINUTES)).isoformat()
    end   = (triggered_at + timedelta(minutes=_WINDOW_MINUTES)).isoformat()

    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"service.keyword": state["service"]}},
                    {"range": {"timestamp": {"gte": start, "lte": end}}}
                ]
            }
        },
        "sort": [{"timestamp": {"order": "asc"}}],
        "size": _MAX_LOGS
    }

    try:
        resp = _es.search(index=_INDEX, body=query)
        raw_logs = [hit["_source"] for hit in resp["hits"]["hits"]]
    except Exception as exc:
        raw_logs = []
        print(f"[log_retrieval] Elasticsearch error: {exc}")

    return {**state, "raw_logs": raw_logs}
