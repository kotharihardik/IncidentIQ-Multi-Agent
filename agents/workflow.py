from langgraph.graph import StateGraph, END

from agents.state import IncidentState
from agents.log_retrieval import log_retrieval_node
from agents.anomaly_detection import anomaly_classification_node
from agents.rag_context import rag_context_node
from agents.root_cause import root_cause_node
from agents.fix_recommendation import fix_recommendation_node
from agents.report_generation import report_generation_node


def build_workflow() -> StateGraph:
    graph = StateGraph(IncidentState)

    # Register nodes
    graph.add_node("log_retrieval", log_retrieval_node)
    graph.add_node("anomaly_classification", anomaly_classification_node)
    graph.add_node("rag_context", rag_context_node)
    graph.add_node("root_cause", root_cause_node)
    graph.add_node("fix_recommendation", fix_recommendation_node)
    graph.add_node("report_generation", report_generation_node)

    # Linear pipeline edges
    graph.set_entry_point("log_retrieval")
    graph.add_edge("log_retrieval", "anomaly_classification")
    graph.add_edge("anomaly_classification", "rag_context")
    graph.add_edge("rag_context", "root_cause")
    graph.add_edge("root_cause", "fix_recommendation")
    graph.add_edge("fix_recommendation", "report_generation")
    graph.add_edge("report_generation", END)

    return graph.compile()


# Singleton — import and call run_pipeline() from anywhere
_workflow = build_workflow()


def run_pipeline(initial_state: dict) -> IncidentState:
    """
    Run the full multi-agent RCA pipeline.

    Parameters
    ----------
    initial_state : dict
        Must contain: incident_id, service, reason, anomaly_score, triggered_at

    Returns
    -------
    IncidentState
        Fully populated state after all agents have run.
    """
    result = _workflow.invoke(initial_state)
    return result
