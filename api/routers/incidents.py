import os
from fastapi import APIRouter, HTTPException, Query
from elasticsearch import Elasticsearch

from api.models.incident import IncidentTrigger, IncidentResponse, LogQueryParams
from api.services.pipeline_service import analyze_incident

router = APIRouter(prefix="/incidents", tags=["incidents"])
_es    = Elasticsearch(os.getenv("ES_HOST", "http://localhost:9200"))
_INDEX = os.getenv("ES_INDEX", "logs")


@router.post("/analyze", response_model=IncidentResponse, status_code=200)
async def analyze(trigger: IncidentTrigger):
    """
    Trigger the full multi-agent RCA pipeline for a reported incident.
    Returns the complete analysis including root cause, fixes, and report.
    """
    try:
        return analyze_incident(trigger)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/logs")
async def get_logs(
    service:    str | None = Query(None),
    level:      str | None = Query(None),
    start_time: str | None = Query(None),
    end_time:   str | None = Query(None),
    size:       int        = Query(50, ge=1, le=500),
):
    """
    Query raw logs from Elasticsearch with optional filters.
    """
    must_clauses = []

    if service:
        must_clauses.append({"term": {"service.keyword": service}})
    if level:
        must_clauses.append({"term": {"level.keyword": level.upper()}})
    if start_time or end_time:
        range_filter: dict = {}
        if start_time:
            range_filter["gte"] = start_time
        if end_time:
            range_filter["lte"] = end_time
        must_clauses.append({"range": {"timestamp": range_filter}})

    query = {
        "query": {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}},
        "sort":  [{"timestamp": {"order": "desc"}}],
        "size":  size,
    }

    try:
        resp = _es.search(index=_INDEX, body=query)
        return {"total": resp["hits"]["total"]["value"],
                "logs":  [h["_source"] for h in resp["hits"]["hits"]]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
