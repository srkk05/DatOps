"""Controlled graph execution for DatOps AgriQuery.

The graph deliberately keeps query planning deterministic and read-only.  The
agent can route a natural-language question through explicit analytical nodes
without generating unrestricted SQL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentState:
    """Mutable state passed between graph nodes."""

    question: str
    cleaned_question: str = ""
    plan: Any = None
    result: Any = None
    summary: str = ""
    validation_status: str = "PENDING"
    trace: list[str] = field(default_factory=list)
    chart_type: str = ""

class AnalyticalGraph:
    """Small explicit state graph used by the AgriQuery runtime.

    This is intentionally a controlled graph rather than an LLM-to-SQL loop:
    each node has one job and the planner still selects from approved query
    plans.  The graph adds inspectable routing/state without sacrificing SQL
    safety or reproducibility.
    """

    def __init__(self, nodes: dict[str, Callable[[AgentState], None]], edges: dict[str, str], conditional_edges: dict[str, Callable[[AgentState], str]]):
        self.nodes = nodes
        self.edges = edges
        self.conditional_edges = conditional_edges

    def run(self, state: AgentState, start: str = "understand") -> AgentState:
        current = start
        while current:
            if current not in self.nodes:
                raise RuntimeError(f"Unknown graph node: {current}")
            state.trace.append(current)
            self.nodes[current](state)
            if current in self.conditional_edges:
                current = self.conditional_edges[current](state)
            else:
                current = self.edges.get(current, "")
        return state


def build_graph(*, clean_question, planner, validator, executor, summarizer) -> AnalyticalGraph:
    """Build the production AgriQuery graph from safe local operations."""

    def understand(state: AgentState) -> None:
        if not state.question or not state.question.strip():
            raise ValueError("Please enter a question.")
        state.cleaned_question = clean_question(state.question)

    def plan(state: AgentState) -> None:
        state.plan = planner(state.question)

    def validate(state: AgentState) -> None:
        if state.plan.data_override is not None:
            state.validation_status = "BYPASSED_DATA_OVERRIDE"
            return
        validator(state.plan.sql)
        state.validation_status = "PASSED_READ_ONLY_SQL"

    def route_after_validation(state: AgentState) -> str:
        return "execute_override" if state.plan.data_override is not None else "execute_sql"

    def execute_override(state: AgentState) -> None:
        state.result = state.plan.data_override.copy()

    def execute_sql(state: AgentState) -> None:
        state.result = executor(state.plan.sql, state.plan.params)

    def visualize(state: AgentState) -> None:
    # The validated query plan determines the appropriate visualization.
        state.chart_type = state.plan.chart

    def explain(state: AgentState) -> None:
        state.summary = summarizer(state.plan.intent, state.result, state.plan)

    return AnalyticalGraph(
        nodes={
            "understand": understand,
            "plan": plan,
            "validate": validate,
            "execute_override": execute_override,
            "execute_sql": execute_sql,
            "visualize": visualize,
            "explain": explain,
        },
        edges={
            "understand": "plan",
            "plan": "validate",
            "execute_override": "visualize",
            "execute_sql": "visualize",
            "visualize": "explain",
            "explain": "",
        },
        conditional_edges={"validate": route_after_validation},
    )


def run_agent_graph(question: str, *, clean_question, planner, validator, executor, summarizer) -> dict[str, Any]:
    """Execute AgriQuery and return the existing public result contract plus trace."""
    graph = build_graph(
        clean_question=clean_question,
        planner=planner,
        validator=validator,
        executor=executor,
        summarizer=summarizer,
    )
    state = graph.run(AgentState(question=question))
    plan = state.plan
    return {
        "question": question,
        "intent": plan.intent,
        "title": plan.title,
        "explanation": plan.explanation,
        "summary": state.summary,
        "chart": state.chart_type,
        "chart_type": state.chart_type,
        "sql": plan.sql.strip(),
        "rows": state.result,
        "data": state.result,
        "row_count": len(state.result),
        "graph_trace": state.trace,
        "validation_status": state.validation_status,
    }
