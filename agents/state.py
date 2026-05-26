from typing import TypedDict, Optional, List


class IncidentState(TypedDict):
    # Input — set by the anomaly consumer before entering the graph
    incident_id: str
    service: str
    reason: str
    anomaly_score: float
    triggered_at: str

    # Stage 1 — raw logs fetched from Elasticsearch
    raw_logs: List[dict]

    # Stage 2 — structured patterns extracted from raw logs
    error_patterns: List[str]       # deduplicated error message templates
    causal_chain: List[str]         # ordered sequence of failure events
    error_rate: float               # fraction of ERROR lines in the window

    # Stage 3 — semantic retrieval from Qdrant
    similar_incidents: List[dict]   # [{summary, root_cause, fix, score}, ...]

    # Stage 4 — RAG context assembled for the LLM
    rag_context: str                # single string injected into the LLM prompt

    # Stage 5 — root cause analysis output
    root_cause: str
    confidence: float               # 0.0 – 1.0
    evidence_logs: List[str]        # log lines that directly support the RCA

    # Stage 6 — fix recommendations
    fix_recommendations: List[str]  # ordered list of remediation steps

    # Stage 7 — final human-readable report
    report: str
