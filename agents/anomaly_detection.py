import re
from collections import Counter
from agents.state import IncidentState

# Templates that map raw error messages to canonical pattern names
_PATTERN_MAP = [
    (re.compile(r"connection.*(timeout|refused|reset)", re.I), "DB connection failure"),
    (re.compile(r"(pool|max.?connections|too many)", re.I),    "Connection pool exhausted"),
    (re.compile(r"out.?of.?memory|OOM|heap",           re.I), "Memory exhaustion"),
    (re.compile(r"(5\d{2}|internal server error)",     re.I), "HTTP 5xx error"),
    (re.compile(r"(timeout|timed.?out)",               re.I), "Request timeout"),
    (re.compile(r"(null.?pointer|attribute.?error|type.?error)", re.I), "Application exception"),
    (re.compile(r"(disk|storage|no space)",            re.I), "Disk space issue"),
    (re.compile(r"(kafka|broker|offset)",              re.I), "Kafka lag / broker issue"),
]


def _classify_message(message: str) -> str:
    for pattern, label in _PATTERN_MAP:
        if pattern.search(message):
            return label
    return "Unknown error"


def anomaly_classification_node(state: IncidentState) -> IncidentState:
    """
    1. Classify each ERROR log line into a canonical pattern.
    2. Count pattern frequencies and keep the top N.
    3. Build a causal chain by ordering events chronologically.
    4. Compute the error rate in the window.
    """
    logs = state.get("raw_logs", [])
    if not logs:
        return {**state, "error_patterns": [], "causal_chain": [], "error_rate": 0.0}

    error_logs = [l for l in logs if l.get("level", "").upper() == "ERROR"]
    error_rate  = len(error_logs) / len(logs) if logs else 0.0

    # Classify and count patterns
    pattern_counts: Counter = Counter()
    for log in error_logs:
        label = _classify_message(log.get("message", ""))
        pattern_counts[label] += 1

    top_patterns = [p for p, _ in pattern_counts.most_common(5)]

    # Build causal chain: deduplicated chronological sequence of error messages
    seen: set = set()
    causal_chain: list = []
    for log in error_logs:
        msg = log.get("message", "")
        label = _classify_message(msg)
        if label not in seen:
            seen.add(label)
            causal_chain.append(f"[{log.get('timestamp','')}] {label}: {msg[:120]}")

    return {
        **state,
        "error_patterns": top_patterns,
        "causal_chain": causal_chain[:10],   # cap at 10 steps
        "error_rate": round(error_rate, 4),
    }
