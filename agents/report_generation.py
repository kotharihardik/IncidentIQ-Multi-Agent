from datetime import datetime, timezone
from agents.state import IncidentState


def report_generation_node(state: IncidentState) -> IncidentState:
    """
    Assemble a structured Markdown incident report from all upstream agent outputs.
    No LLM call needed — this is purely deterministic template rendering.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    confidence_pct = int(state.get("confidence", 0.0) * 100)

    # Fix steps formatted as numbered list
    fixes = state.get("fix_recommendations", [])
    fix_block = "\n".join(f"{i+1}. {f}" for i, f in enumerate(fixes)) or "No fixes available."

    # Evidence logs
    evidence = state.get("evidence_logs", [])
    evidence_block = "\n".join(f"  - {e}" for e in evidence) or "  - No evidence captured."

    # Similar incidents summary
    similar = state.get("similar_incidents", [])
    similar_block = ""
    if similar:
        lines = []
        for i, s in enumerate(similar[:3], 1):
            lines.append(f"  {i}. [{s['score']}] {s['summary']}")
        similar_block = "\n".join(lines)
    else:
        similar_block = "  None found."

    report = f"""# Incident Report — {state['service']}

**Incident ID**  : {state['incident_id']}
**Triggered At** : {state['triggered_at']}
**Report At**    : {now}
**Anomaly Score**: {state['anomaly_score']}

---

## Affected Service
`{state['service']}`

## Error Summary
- **Error rate in window** : {round(state.get('error_rate', 0) * 100, 1)}%
- **Top error patterns**   : {', '.join(state.get('error_patterns', []))}

## Causal Chain
{chr(10).join('- ' + c for c in state.get('causal_chain', []))}

---

## Root Cause Analysis
**Root Cause** : {state.get('root_cause', 'Unknown')}
**Confidence** : {confidence_pct}%

### Supporting Evidence
{evidence_block}

---

## Similar Historical Incidents
{similar_block}

---

## Recommended Actions
{fix_block}

---

*Report generated automatically by IncidentIQ Multi-Agent System*
"""

    return {**state, "report": report}
