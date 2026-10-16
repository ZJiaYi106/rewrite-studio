from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.nodes.assemble import assemble_node
from agent.nodes.image import image_process_node
from agent.nodes.parse import parse_node
from agent.nodes.rewrite import rewrite_node
from agent.state import AgentState


def should_continue_after_parse(state: AgentState) -> str:
    if state.get("parse_error") or not state.get("content_markdown"):
        return "fail"
    return "continue"


def mark_parse_failure(state: AgentState) -> dict:
    errors = list(state.get("errors", []))
    error = state.get("parse_error") or "文章解析失败"
    if error not in errors:
        errors.append(error)
    return {"status": "failed", "errors": errors}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("parse", parse_node)
    graph.add_node("mark_parse_failure", mark_parse_failure)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("process_images", image_process_node)
    graph.add_node("assemble", assemble_node)

    graph.add_edge(START, "parse")
    graph.add_conditional_edges(
        "parse",
        should_continue_after_parse,
        {"continue": "rewrite", "fail": "mark_parse_failure"},
    )
    graph.add_edge("mark_parse_failure", END)
    graph.add_edge("rewrite", "process_images")
    graph.add_edge("process_images", "assemble")
    graph.add_edge("assemble", END)
    return graph.compile()
