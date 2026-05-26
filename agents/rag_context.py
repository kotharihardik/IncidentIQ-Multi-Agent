import os
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

from agents.state import IncidentState

_model  = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
_qdrant = QdrantClient(url=os.getenv("QDRANT_HOST", "http://localhost:6333"))
_COLLECTION = os.getenv("QDRANT_COLLECTION", "incidents")
_TOP_K = 5


def _build_query_text(state: IncidentState) -> str:
    patterns = ", ".join(state.get("error_patterns", []))
    chain    = " → ".join(
        [c.split("]: ", 1)[-1] for c in state.get("causal_chain", [])[:3]]
    )
    return f"Service: {state['service']}. Errors: {patterns}. Chain: {chain}"


def rag_context_node(state: IncidentState) -> IncidentState:
    """
    1. Embed a compact incident summary.
    2. Query Qdrant for top-K similar historical incidents.
    3. Assemble a RAG context string for the LLM.
    """
    query_text = _build_query_text(state)
    vector = _model.encode(query_text).tolist()

    try:
        results = _qdrant.search(
            collection_name=_COLLECTION,
            query_vector=vector,
            limit=_TOP_K,
            with_payload=True,
        )
        similar = [
            {
                "summary":    r.payload.get("summary", ""),
                "root_cause": r.payload.get("root_cause", ""),
                "fix":        r.payload.get("fix", ""),
                "score":      round(r.score, 4),
            }
            for r in results
        ]
    except Exception as exc:
        print(f"[rag_context] Qdrant error: {exc}")
        similar = []

    # Build the context block that will be injected into the LLM prompt
    lines = [
        f"=== Current Incident ===",
        f"Service      : {state['service']}",
        f"Anomaly score: {state['anomaly_score']}",
        f"Error rate   : {state['error_rate']}",
        f"Patterns     : {', '.join(state.get('error_patterns', []))}",
        "",
        "=== Causal Chain (chronological) ===",
    ]
    for step in state.get("causal_chain", []):
        lines.append(f"  {step}")

    if similar:
        lines += ["", "=== Similar Past Incidents (ranked by similarity) ==="]
        for i, s in enumerate(similar, 1):
            lines += [
                f"[{i}] Score {s['score']}",
                f"    Summary   : {s['summary']}",
                f"    Root cause: {s['root_cause']}",
                f"    Fix       : {s['fix']}",
            ]

    rag_context = "\n".join(lines)

    return {**state, "similar_incidents": similar, "rag_context": rag_context}
