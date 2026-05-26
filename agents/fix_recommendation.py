import os
import json
from openai import OpenAI

from agents.state import IncidentState

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_MODEL  = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_SYSTEM_PROMPT = """You are a senior DevOps engineer.

Given a root cause and historical fix examples, produce a prioritised list of
remediation steps. Be specific and actionable — no vague advice.

Respond ONLY with a valid JSON array of strings — no markdown, no extra text:
["Step 1: ...", "Step 2: ...", "Step 3: ..."]

Rules:
- Maximum 6 steps
- Immediate mitigations first, long-term fixes last
- Each step must be one sentence and start with an imperative verb
"""

# Rule-based fallback: map known root causes → canned fixes
_KNOWN_FIXES = {
    "DB connection failure":       [
        "Restart the database connection pool in the affected service.",
        "Check the database server health and connectivity from the service pod.",
        "Review database max_connections setting and increase if below 200.",
    ],
    "Connection pool exhausted":   [
        "Increase DB pool size (e.g. SQLALCHEMY_POOL_SIZE=20).",
        "Enable connection timeout + recycling (POOL_RECYCLE=300).",
        "Add Redis caching layer to reduce DB query volume.",
        "Identify and fix slow queries causing long-held connections.",
    ],
    "Memory exhaustion":           [
        "Restart the affected pod immediately to free memory.",
        "Increase memory limit in the Kubernetes deployment manifest.",
        "Profile the service for memory leaks with memory_profiler.",
    ],
    "Request timeout":             [
        "Check downstream service health and latency.",
        "Increase timeout threshold in the calling service.",
        "Add circuit breaker (e.g. tenacity or resilience4j) around the call.",
    ],
    "Kafka lag / broker issue":    [
        "Scale up consumer group replicas to reduce lag.",
        "Check broker disk space and clear old topic segments if needed.",
        "Review consumer code for blocking calls inside the poll loop.",
    ],
}


def fix_recommendation_node(state: IncidentState) -> IncidentState:
    """
    1. Try LLM-based fix generation using root cause + similar incident fixes.
    2. Fall back to rule-based lookup if LLM fails.
    """
    # Build prompt context
    historical_fixes = "\n".join(
        f"- {s['fix']}" for s in state.get("similar_incidents", []) if s.get("fix")
    )
    user_prompt = (
        f"Root cause: {state.get('root_cause', 'Unknown')}\n\n"
        f"Historical fixes from similar incidents:\n{historical_fixes or 'None available'}"
    )

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
        )
        raw  = response.choices[0].message.content.strip()
        fixes = json.loads(raw)
        if not isinstance(fixes, list):
            raise ValueError("Expected JSON array")

    except Exception as exc:
        print(f"[fix_recommendation] LLM error: {exc}")
        # Rule-based fallback
        root_cause = state.get("root_cause", "")
        fixes = []
        for key, steps in _KNOWN_FIXES.items():
            if key.lower() in root_cause.lower():
                fixes = steps
                break
        if not fixes:
            fixes = ["Investigate service logs manually.", "Escalate to on-call engineer."]

    return {**state, "fix_recommendations": fixes}
