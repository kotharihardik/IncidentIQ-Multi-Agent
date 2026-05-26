import uuid
from datetime import datetime, timezone

from agents.workflow import run_pipeline
from api.models.incident import IncidentTrigger, IncidentResponse


def analyze_incident(trigger: IncidentTrigger) -> IncidentResponse:
    """
    Build the initial state, run the full LangGraph pipeline,
    and return a typed response object.
    """
    incident_id  = str(uuid.uuid4())
    triggered_at = trigger.triggered_at or datetime.now(timezone.utc).isoformat()

    initial_state = {
        "incident_id":   incident_id,
        "service":       trigger.service,
        "reason":        trigger.reason,
        "anomaly_score": trigger.anomaly_score,
        "triggered_at":  triggered_at,
        # remaining fields populated by the graph nodes
        "raw_logs":             [],
        "error_patterns":       [],
        "causal_chain":         [],
        "error_rate":           0.0,
        "similar_incidents":    [],
        "rag_context":          "",
        "root_cause":           "",
        "confidence":           0.0,
        "evidence_logs":        [],
        "fix_recommendations":  [],
        "report":               "",
    }

    final_state = run_pipeline(initial_state)
    completed_at = datetime.now(timezone.utc).isoformat()

    return IncidentResponse(
        incident_id=incident_id,
        service=final_state["service"],
        root_cause=final_state["root_cause"],
        confidence=final_state["confidence"],
        error_rate=final_state["error_rate"],
        error_patterns=final_state["error_patterns"],
        fix_recommendations=final_state["fix_recommendations"],
        report=final_state["report"],
        triggered_at=triggered_at,
        completed_at=completed_at,
    )
