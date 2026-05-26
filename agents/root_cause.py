import os
import json
from openai import OpenAI

from agents.state import IncidentState

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_MODEL  = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_SYSTEM_PROMPT = """You are a senior site-reliability engineer performing root cause analysis.

You will receive:
- A structured incident summary (service, error patterns, causal chain)
- A set of similar historical incidents retrieved from a knowledge base

Your job is to reason step-by-step and identify the single most likely root cause.

Respond ONLY with a valid JSON object — no markdown, no extra text:
{
  "root_cause": "<one concise sentence>",
  "confidence": <float 0.0–1.0>,
  "evidence_logs": ["<log line 1>", "<log line 2>", ...]
}

Rules:
- confidence > 0.8 means you are highly certain
- evidence_logs must be copied verbatim from the causal chain provided
- If similar incidents point to the same cause, raise confidence
"""


def root_cause_node(state: IncidentState) -> IncidentState:
    """
    Send the RAG context to the LLM and parse the structured JSON response.
    Falls back to a rule-based guess if the LLM call fails.
    """
    user_prompt = state.get("rag_context", "No context available.")

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            temperature=0.0,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        root_cause    = parsed.get("root_cause", "Unknown")
        confidence    = float(parsed.get("confidence", 0.5))
        evidence_logs = parsed.get("evidence_logs", [])

    except Exception as exc:
        print(f"[root_cause] LLM error: {exc}")
        # Fallback: use the dominant pattern
        patterns = state.get("error_patterns", ["Unknown"])
        root_cause    = f"Suspected: {patterns[0]}" if patterns else "Unknown"
        confidence    = 0.3
        evidence_logs = state.get("causal_chain", [])[:3]

    return {
        **state,
        "root_cause":    root_cause,
        "confidence":    confidence,
        "evidence_logs": evidence_logs,
    }
