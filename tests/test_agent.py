from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import pytest

from src.agent_graph import AgentState, build_graph
from src import agent


@dataclass
class FakePlan:
    intent: str = "test"
    sql: str = "SELECT 1 AS value"
    title: str = "Test"
    explanation: str = "Test explanation"
    chart: str = "table"
    params: tuple = ()
    data_override: pd.DataFrame | None = None


def test_graph_routes_sql_path_and_records_trace():
    plan = FakePlan()
    state = AgentState(question="show me something")

    graph = build_graph(
        clean_question=lambda q: q.lower(),
        planner=lambda q: plan,
        validator=lambda sql: None,
        executor=lambda sql, params: pd.DataFrame({"value": [1]}),
        summarizer=lambda intent, df, p: "one result",
    )

    result = graph.run(state)

    assert result.cleaned_question == "show me something"
    assert result.validation_status == "PASSED_READ_ONLY_SQL"
    assert result.result.iloc[0]["value"] == 1
    assert result.summary == "one result"
    assert result.trace == [
        "understand", "plan", "validate", "execute_sql", "visualize", "explain"
    ]


def test_graph_routes_data_override_without_sql_execution():
    plan = FakePlan(data_override=pd.DataFrame({"value": [42]}))
    executed = []
    state = AgentState(question="risk")

    graph = build_graph(
        clean_question=lambda q: q.lower(),
        planner=lambda q: plan,
        validator=lambda sql: (_ for _ in ()).throw(AssertionError("should not validate override")),
        executor=lambda sql, params: executed.append(True),
        summarizer=lambda intent, df, p: "override result",
    )

    result = graph.run(state)

    assert result.validation_status == "BYPASSED_DATA_OVERRIDE"
    assert result.result.iloc[0]["value"] == 42
    assert executed == []
    assert result.trace == [
        "understand", "plan", "validate", "execute_override", "visualize", "explain"
    ]


def test_graph_rejects_unsafe_sql_before_execution():
    state = AgentState(question="delete everything")
    graph = build_graph(
        clean_question=lambda q: q.lower(),
        planner=lambda q: FakePlan(sql="DELETE FROM arrivals"),
        validator=agent._validate_sql,
        executor=lambda sql, params: pytest.fail("unsafe SQL reached executor"),
        summarizer=lambda intent, df, p: "never reached",
    )

    with pytest.raises(ValueError, match="Only read-only|Unsafe SQL"):
        graph.run(state)


def test_supported_queries_keep_chart_selection():
    top = agent.plan_question("Top 5 mandis by arrivals")
    daily = agent.plan_question("Show wheat arrivals for the last 30 days")
    price = agent.plan_question("What is the wheat price?")

    assert top.intent == "top_mandis"
    assert top.chart == "bar"
    assert daily.intent == "daily_arrivals"
    assert daily.chart == "line"
    assert price.intent == "price_summary"
    assert price.chart == "price_comparison"


def test_run_question_exposes_graph_trace_and_existing_result_contract(monkeypatch):
    fake_plan = FakePlan(
        intent="top_mandis",
        sql="SELECT 1 AS value",
        title="Top",
        explanation="Grounded",
        chart="bar",
    )

    class FakeConnection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def execute(self, sql, params):
            class Result:
                def df(self):
                    return pd.DataFrame({"value": [1]})
            return Result()

    monkeypatch.setattr(agent, "plan_question", lambda q: fake_plan)
    monkeypatch.setattr(agent, "get_connection", lambda: FakeConnection())

    result = agent.run_question("top")

    assert result["intent"] == "top_mandis"
    assert result["chart_type"] == "bar"
    assert result["row_count"] == 1
    assert result["validation_status"] == "PASSED_READ_ONLY_SQL"
    assert result["graph_trace"] == [
        "understand", "plan", "validate", "execute_sql", "visualize", "explain"
    ]
