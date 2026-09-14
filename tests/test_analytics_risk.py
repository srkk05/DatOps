import pandas as pd
import pytest

from src import analytics, risk_engine


def test_percentile_score_is_bounded():
    scores = risk_engine.percentile_score(pd.Series([10, 20, 30, 40, 50]))
    assert scores.notna().all()
    assert scores.between(0, 100).all()


def test_single_percentile_observation_is_neutral():
    scores = risk_engine.percentile_score(pd.Series([42]))
    assert float(scores.iloc[0]) == 50.0


def test_weighted_score_renormalizes_missing_components():
    a = pd.Series([80.0, None])
    b = pd.Series([20.0, 60.0])
    result = risk_engine.weighted_score([(a, 0.5), (b, 0.5)])
    assert round(float(result.iloc[0]), 2) == 50.0
    assert round(float(result.iloc[1]), 2) == 60.0


@pytest.mark.parametrize(
    "score, label",
    [
        (90, "HIGH"),
        (70, "ELEVATED"),
        (45, "WATCH"),
        (10, "LOW"),
        (None, "INSUFFICIENT DATA"),
    ],
)
def test_stress_labels(score, label):
    assert risk_engine.stress_label(score) == label


def test_arrival_shock_direction_and_coverage(monkeypatch):
    daily = pd.DataFrame(
        {
            "mandi_id": ["M1", "M1", "M1", "M1", "M1", "M1"],
            "arrival_date": pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-01-31",
                    "2026-02-01",
                    "2026-02-02",
                ]
            ),
            "arrivals_qtl": [100, 100, 100, 200, 200, 200],
        }
    )

    class FakeResult:
        def fetchdf(self):
            # This mimics the SQL output after aggregation.
            return pd.DataFrame(
                {
                    "mandi_id": ["M1"],
                    "mandi_name": ["Test Mandi"],
                    "district": ["Test"],
                    "state": ["Test"],
                    "latest_arrival_date": [pd.Timestamp("2026-02-02")],
                    "window_days": [30],
                    "recent_total_qtl": [600.0],
                    "recent_observed_days": [3],
                    "baseline_total_qtl": [300.0],
                    "baseline_observed_days": [3],
                    "recent_avg_daily_qtl": [200.0],
                    "baseline_avg_daily_qtl": [100.0],
                }
            )

    class FakeConnection:
        def execute(self, query):
            return FakeResult()

        def close(self):
            pass

    monkeypatch.setattr(analytics, "get_connection", lambda: FakeConnection())
    result = analytics.arrival_shock_by_mandi(window_days=30, min_observed_days=3)

    assert len(result) == 1
    assert result.iloc[0]["shock_direction"] == "SURGE"
    assert round(float(result.iloc[0]["shock_pct"]), 1) == 100.0
    assert result.iloc[0]["shock_confidence"] == "LOW"


def test_action_engine_prioritizes_combined_negative_shock(monkeypatch):
    risk = pd.DataFrame(
        {
            "mandi_id": ["M1"],
            "mandi_name": ["Test Mandi"],
            "district": ["Test"],
            "state": ["Test"],
            "operational_risk_score": [85.0],
            "operational_risk": ["HIGH"],
            "market_stress_score": [75.0],
            "logistics_stress_score": [90.0],
        }
    )

    shock = pd.DataFrame(
        {
            "mandi_id": ["M1"],
            "latest_arrival_date": [pd.Timestamp("2026-02-02")],
            "window_days": [30],
            "recent_avg_daily_qtl": [70.0],
            "baseline_avg_daily_qtl": [100.0],
            "shock_pct": [-30.0],
            "abs_shock_pct": [30.0],
            "shock_direction": ["DROP"],
            "coverage_pct": [40.0],
            "shock_confidence": ["HIGH"],
        }
    )

    monkeypatch.setattr(risk_engine, "mandi_operational_risk", lambda: risk)
    monkeypatch.setattr(analytics, "arrival_shock_by_mandi", lambda: shock)

    result = risk_engine.action_engine()

    assert result.iloc[0]["action_priority"] == "CRITICAL"
    assert "arrival drop" in result.iloc[0]["recommended_action"].lower()
    assert "alternate transport" in result.iloc[0]["recommended_action"].lower()


def test_transport_analytics_queries_use_destination_warehouse(monkeypatch):
    class FakeResult:
        def fetchdf(self):
            return pd.DataFrame({"destination_warehouse": ["WH-North"], "trips": [10]})

    class FakeConnection:
        def __init__(self):
            self.queries = []
        def execute(self, query):
            self.queries.append(query)
            return FakeResult()
        def close(self):
            pass

    fake = FakeConnection()
    monkeypatch.setattr(analytics, "get_connection", lambda: fake)
    wh = analytics.warehouse_logistics()
    routes = analytics.route_logistics(min_trips=10)
    assert not wh.empty
    assert not routes.empty
    assert all("destination_warehouse" in q for q in fake.queries)
