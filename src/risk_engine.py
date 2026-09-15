"""
Calculate system-level weather stress by IST date.

Weather observations are not attributed to individual mandis.
District-level weather analysis uses the tracked synthetic
sensor -> district mapping permitted by the dataset notes.

Components:
    - maximum valid rainfall across sensors
    - percentage of reporting observations with valid rainfall > 0

This is a monitoring signal, not a claim that rainfall caused arrivals
to change.
"""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Optional

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "datops.duckdb"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------

def get_connection():
    """Open the curated DuckDB database in read-only mode."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"DuckDB database not found: {DB_PATH}. "
            "Run `python src/database.py` first."
        )

    return duckdb.connect(str(DB_PATH), read_only=True)


# ---------------------------------------------------------------------
# Generic scoring helpers
# ---------------------------------------------------------------------

def _clip_score(value: float) -> float:
    """Keep a score inside the documented 0-100 range."""
    return float(max(0.0, min(100.0, value)))


def percentile_score(series: pd.Series) -> pd.Series:
    """
    Convert a numeric series to a relative 0-100 percentile score.

    Ties receive the average rank. A single observation receives 50 rather
    than an artificial 0 or 100 because there is no meaningful peer ranking.
    """
    values = pd.to_numeric(series, errors="coerce")

    valid = values.notna()
    result = pd.Series(pd.NA, index=series.index, dtype="Float64")

    n = int(valid.sum())

    if n == 0:
        return result

    if n == 1:
        result.loc[valid] = 50.0
        return result

    ranks = values.loc[valid].rank(method="average", pct=True) * 100
    result.loc[valid] = ranks.round(2)

    return result


def weighted_score(
    components: list[tuple[pd.Series, float]],
) -> pd.Series:
    """
    Weighted average of component scores.

    Missing components are excluded and the remaining weights are
    re-normalized. This prevents missing data from silently becoming zero
    stress.
    """
    if not components:
        return pd.Series(dtype="Float64")

    frame = pd.DataFrame(
        {
            f"component_{i}": score.astype("Float64")
            for i, (score, _) in enumerate(components)
        }
    )

    weights = pd.Series(
        {
            f"component_{i}": float(weight)
            for i, (_, weight) in enumerate(components)
        }
    )

    numerator = frame.mul(weights, axis=1).sum(axis=1, min_count=1)

    available_weights = frame.notna().mul(weights, axis=1).sum(axis=1)

    result = numerator.div(
        available_weights.where(available_weights > 0)
    )

    return result.clip(0, 100).round(2)


def stress_label(score: Optional[float]) -> str:
    """Human-readable interpretation of a 0-100 relative stress score."""
    if score is None or pd.isna(score):
        return "INSUFFICIENT DATA"

    score = float(score)

    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "ELEVATED"
    if score >= 40:
        return "WATCH"
    return "LOW"


# ---------------------------------------------------------------------
# Market stress
# ---------------------------------------------------------------------

def market_stress_by_mandi() -> pd.DataFrame:
    """
    Calculate relative market stress for each mandi.

    Components:
        - below_msp_rate: higher = more pressure
        - negative_msp_gap_pct: larger negative gap = more pressure

    Both components are ranked relative to the observed mandi population.
    """
    con = get_connection()

    query = """
        WITH price_base AS (
            SELECT
                p.mandi_id,
                p.modal_price,
                p.msp
            FROM prices p
            WHERE p.modal_price IS NOT NULL
              AND p.msp IS NOT NULL
        ),
        mandi_market AS (
            SELECT
                mandi_id,
                COUNT(*) AS price_observations,
                AVG(
                    CASE
                        WHEN modal_price < msp THEN 1.0
                        ELSE 0.0
                    END
                ) * 100 AS below_msp_rate,
                AVG(modal_price - msp) AS avg_msp_gap,
                AVG(
                    CASE
                        WHEN msp <> 0
                        THEN (modal_price - msp) / msp * 100
                    END
                ) AS avg_msp_gap_pct
            FROM price_base
            GROUP BY mandi_id
        )
        ,master_dedup AS (
            SELECT
                mandi_id,
                MAX(mandi_name) AS mandi_name,
                MAX(district) AS district,
                MAX(state) AS state
            FROM mandi_master
            GROUP BY mandi_id
        )
        SELECT
            mm.mandi_id,
            m.mandi_name,
            m.district,
            m.state,
            mm.price_observations,
            mm.below_msp_rate,
            mm.avg_msp_gap,
            mm.avg_msp_gap_pct
        FROM mandi_market mm
        LEFT JOIN master_dedup m
            ON mm.mandi_id = m.mandi_id
        ORDER BY mm.below_msp_rate DESC
    """

    try:
        df = con.execute(query).fetchdf()
    finally:
        con.close()

    if df.empty:
        return df

    # Negative gap is pressure. Flip its sign so larger = more pressure.
    negative_gap = -pd.to_numeric(
        df["avg_msp_gap_pct"], errors="coerce"
    )

    below_score = percentile_score(df["below_msp_rate"])
    gap_score = percentile_score(negative_gap)

    df["market_below_msp_score"] = below_score
    df["market_gap_score"] = gap_score

    df["market_stress_score"] = weighted_score(
        [
            (below_score, 0.70),
            (gap_score, 0.30),
        ]
    )

    df["market_stress"] = df["market_stress_score"].apply(
        lambda x: stress_label(x)
    )

    df["market_reason"] = df.apply(
        lambda row: (
            f"{row['below_msp_rate']:.1f}% of available price observations "
            f"are below MSP; average modal price is "
            f"{row['avg_msp_gap_pct']:+.1f}% vs MSP."
        ),
        axis=1,
    )

    return df


# ---------------------------------------------------------------------
# Logistics stress
# ---------------------------------------------------------------------

def logistics_stress_by_mandi() -> pd.DataFrame:
    """
    Calculate relative logistics stress for each mandi.

    Components:
        - average transit time percentile
        - delay rate percentile

    Delay is defined consistently with the project analytics layer:
        transit_hours > empirical P90 transit threshold.
    """
    con = get_connection()

    try:
        p90 = con.execute(
            """
            SELECT quantile_cont(transit_hours, 0.90) AS p90
            FROM transport
            WHERE transit_status = 'VALID'
              AND transit_hours IS NOT NULL
            """
        ).fetchone()[0]

        if p90 is None:
            return pd.DataFrame()

        query = """
            WITH master_dedup AS (
                SELECT
                    mandi_id,
                    MAX(mandi_name) AS mandi_name,
                    MAX(district) AS district,
                    MAX(state) AS state
                FROM mandi_master
                GROUP BY mandi_id
            )
            SELECT
                t.mandi_id,
                m.mandi_name,
                m.district,
                m.state,
                COUNT(*) AS transport_records,
                AVG(t.transit_hours) AS avg_transit_hours,
                MEDIAN(t.transit_hours) AS median_transit_hours,
                AVG(
                    CASE
                        WHEN t.transit_hours > ?
                        THEN 1.0
                        ELSE 0.0
                    END
                ) * 100 AS delay_rate
            FROM transport t
            LEFT JOIN master_dedup m
                ON t.mandi_id = m.mandi_id
            WHERE t.transit_status = 'VALID'
              AND t.transit_hours IS NOT NULL
            GROUP BY
                t.mandi_id,
                m.mandi_name,
                m.district,
                m.state
            ORDER BY avg_transit_hours DESC
        """

        df = con.execute(query, [float(p90)]).fetchdf()
    finally:
        con.close()

    if df.empty:
        return df

    transit_score = percentile_score(df["avg_transit_hours"])
    delay_score = percentile_score(df["delay_rate"])

    df["logistics_transit_score"] = transit_score
    df["logistics_delay_score"] = delay_score

    df["logistics_stress_score"] = weighted_score(
        [
            (transit_score, 0.60),
            (delay_score, 0.40),
        ]
    )

    df["logistics_stress"] = df["logistics_stress_score"].apply(
        lambda x: stress_label(x)
    )

    df["logistics_reason"] = df.apply(
        lambda row: (
            f"Average transit is {row['avg_transit_hours']:.1f}h with "
            f"{row['delay_rate']:.1f}% of valid movements above the "
            f"dataset P90 threshold of {float(p90):.1f}h."
        ),
        axis=1,
    )

    df["p90_threshold_hours"] = float(p90)

    return df


# ---------------------------------------------------------------------
# Weather stress
# ---------------------------------------------------------------------

def weather_stress() -> pd.DataFrame:
    """
    Calculate system-level weather stress by IST date.

    Weather is intentionally NOT attributed to individual mandis because
    the supplied workbook contains sensor IDs but no direct sensor-to-mandi
    geographic mapping.

    Components:
        - maximum valid rainfall across sensors
        - percentage of reporting sensors with valid rainfall > 0

    This is a monitoring signal, not a claim that rainfall caused arrivals
    to change.
    """
    con = get_connection()

    query = """
        SELECT
            weather_date_ist,
            AVG(temperature_c) AS avg_temperature_c,
            AVG(
                CASE
                    WHEN rainfall_status = 'VALID'
                    THEN rainfall_mm
                END
            ) AS avg_rainfall_mm,
            MAX(
                CASE
                    WHEN rainfall_status = 'VALID'
                    THEN rainfall_mm
                END
            ) AS max_rainfall_mm,
            COUNT(
                DISTINCT CASE
                    WHEN rainfall_status = 'VALID'
                    THEN sensor_id
                END
            ) AS valid_rainfall_sensors,
            COUNT(
                DISTINCT sensor_id
            ) AS reporting_sensors,
            SUM(
                CASE
                    WHEN rainfall_status = 'VALID'
                     AND rainfall_mm > 0
                    THEN 1
                    ELSE 0
                END
            ) AS rainy_sensor_observations,
            COUNT(
                CASE
                    WHEN rainfall_status = 'VALID'
                    THEN 1
                END
            ) AS valid_rainfall_observations
        FROM weather
        WHERE weather_date_ist IS NOT NULL
        GROUP BY weather_date_ist
        ORDER BY weather_date_ist
    """

    try:
        df = con.execute(query).fetchdf()
    finally:
        con.close()

    if df.empty:
        return df

    df["rainy_sensor_share_pct"] = (
        pd.to_numeric(
            df["rainy_sensor_observations"],
            errors="coerce",
        )
        / pd.to_numeric(
            df["valid_rainfall_observations"],
            errors="coerce",
        ).replace(0, pd.NA)
        * 100
    )

    rainfall_score = percentile_score(
        df["max_rainfall_mm"]
    )
    coverage_score = percentile_score(
        df["rainy_sensor_share_pct"]
    )

    df["weather_rainfall_score"] = rainfall_score
    df["weather_coverage_score"] = coverage_score

    df["weather_stress_score"] = weighted_score(
        [
            (rainfall_score, 0.70),
            (coverage_score, 0.30),
        ]
    )

    df["weather_stress"] = df["weather_stress_score"].apply(
        lambda x: stress_label(x)
    )

    df["weather_reason"] = df.apply(
        lambda row: (
            f"Maximum valid sensor rainfall was "
            f"{row['max_rainfall_mm']:.1f} mm and "
            f"{row['rainy_sensor_share_pct']:.1f}% of valid "
            f"sensor observations recorded rainfall."
        ),
        axis=1,
    )

    return df


# ---------------------------------------------------------------------
# Mandi operational risk
# ---------------------------------------------------------------------

def mandi_operational_risk() -> pd.DataFrame:
    """
    Combine market and logistics stress at mandi level.

    Weather is excluded here because the tracked weather mapping supports
    district-level attribution, not defensible mandi-level attribution.
    Weather is therefore retained as a system-level signal.

    Weighting:
        market stress   50%
        logistics stress 50%

    This is an operational prioritization score, not a probability of loss.
    """
    market = market_stress_by_mandi()
    logistics = logistics_stress_by_mandi()

    if market.empty and logistics.empty:
        return pd.DataFrame()

    if market.empty:
        result = logistics.copy()
        result["operational_risk_score"] = result[
            "logistics_stress_score"
        ]
        result["operational_risk"] = result[
            "operational_risk_score"
        ].apply(stress_label)
        result["operational_risk_reason"] = result[
            "logistics_reason"
        ]
        return result

    if logistics.empty:
        result = market.copy()
        result["operational_risk_score"] = result[
            "market_stress_score"
        ]
        result["operational_risk"] = result[
            "operational_risk_score"
        ].apply(stress_label)
        result["operational_risk_reason"] = result[
            "market_reason"
        ]
        return result

    result = market.merge(
        logistics,
        on=["mandi_id", "mandi_name", "district", "state"],
        how="outer",
        suffixes=("_market", "_logistics"),
    )

    result["operational_risk_score"] = weighted_score(
        [
            (result["market_stress_score"], 0.50),
            (result["logistics_stress_score"], 0.50),
        ]
    )

    result["operational_risk"] = result[
        "operational_risk_score"
    ].apply(stress_label)

    def reason(row):
        parts = []

        if pd.notna(row.get("market_stress_score")):
            parts.append(
                f"market stress {row['market_stress_score']:.0f}/100"
            )

        if pd.notna(row.get("logistics_stress_score")):
            parts.append(
                f"logistics stress "
                f"{row['logistics_stress_score']:.0f}/100"
            )

        return " · ".join(parts)

    result["operational_risk_reason"] = result.apply(
        reason,
        axis=1,
    )

    return result.sort_values(
        "operational_risk_score",
        ascending=False,
    )


# ---------------------------------------------------------------------
# Action engine: combine explainable risk with arrival shocks
# ---------------------------------------------------------------------

def action_engine() -> pd.DataFrame:
    """Return ranked operational actions by mandi.

    The action layer deliberately uses existing explainable signals only:
    operational risk + arrival shock. It does not claim to forecast demand,
    prices, weather or failure probability.
    """
    from src.analytics import arrival_shock_by_mandi

    risk = mandi_operational_risk().copy()
    shock = arrival_shock_by_mandi().copy()
    if risk.empty and shock.empty:
        return pd.DataFrame()
    if risk.empty:
        result = shock.copy()
        result["operational_risk_score"] = pd.NA
        result["operational_risk"] = "INSUFFICIENT DATA"
    elif shock.empty:
        result = risk.copy()
        result["shock_pct"] = pd.NA
        result["shock_direction"] = "INSUFFICIENT DATA"
        result["shock_confidence"] = "INSUFFICIENT DATA"
    else:
        result = risk.merge(
            shock[["mandi_id", "latest_arrival_date", "window_days",
                   "recent_avg_daily_qtl", "baseline_avg_daily_qtl",
                   "shock_pct", "abs_shock_pct", "shock_direction",
                   "coverage_pct", "shock_confidence"]],
            on="mandi_id", how="outer", suffixes=("", "_arrival")
        )

    def priority(row):
        risk_score = pd.to_numeric(row.get("operational_risk_score"), errors="coerce")
        shock_pct = pd.to_numeric(row.get("shock_pct"), errors="coerce")
        if pd.notna(risk_score) and pd.notna(shock_pct) and risk_score >= 80 and abs(shock_pct) >= 20:
            return "CRITICAL"
        if (pd.notna(risk_score) and risk_score >= 80) or (pd.notna(shock_pct) and abs(shock_pct) >= 40):
            return "HIGH"
        if (pd.notna(risk_score) and risk_score >= 60) or (pd.notna(shock_pct) and abs(shock_pct) >= 20):
            return "ELEVATED"
        return "WATCH"

    def action(row):
        risk_score = pd.to_numeric(row.get("operational_risk_score"), errors="coerce")
        shock = pd.to_numeric(row.get("shock_pct"), errors="coerce")
        market = pd.to_numeric(row.get("market_stress_score"), errors="coerce")
        logistics = pd.to_numeric(row.get("logistics_stress_score"), errors="coerce")
        if pd.notna(shock) and shock <= -20 and pd.notna(logistics) and logistics >= 60:
            return "Investigate the arrival drop and prioritize alternate transport/sourcing capacity."
        if pd.notna(shock) and shock <= -20 and pd.notna(market) and market >= 60:
            return "Validate the supply shortfall and review procurement/market intervention options."
        if pd.notna(shock) and shock >= 20 and pd.notna(logistics) and logistics >= 60:
            return "Prepare for higher inbound volume and monitor congestion / turnaround capacity."
        if pd.notna(risk_score) and risk_score >= 80:
            return "Escalate for operational review; address the dominant market/logistics stress signal."
        if pd.notna(shock) and abs(shock) >= 20:
            return "Monitor the arrival anomaly and validate the underlying daily records."
        return "Routine monitoring."

    result["action_priority"] = result.apply(priority, axis=1)
    result["recommended_action"] = result.apply(action, axis=1)
    result["action_reason"] = result.apply(
        lambda r: (
            f"Risk {r['operational_risk_score']:.1f}/100" if pd.notna(r.get("operational_risk_score")) else "Risk signal unavailable"
        ) + (
            f" · arrivals {r['shock_pct']:+.1f}% vs prior window" if pd.notna(r.get("shock_pct")) else " · arrival shock unavailable"
        ), axis=1
    )
    order = pd.CategoricalDtype(["CRITICAL", "HIGH", "ELEVATED", "WATCH"], ordered=True)
    result["action_priority"] = result["action_priority"].astype(order)
    return result.sort_values(["action_priority", "operational_risk_score", "abs_shock_pct"], ascending=[True, False, False], na_position="last").reset_index(drop=True)


# ---------------------------------------------------------------------
# System-level risk
# ---------------------------------------------------------------------

def system_risk_summary() -> dict:
    """
    Return a system-level summary.

    Because the available weather mapping does not support defensible
    mandi-level attribution, weather contributes to system-level risk only.
    District-level weather analysis remains available separately.
        
    We use the latest weather stress observation and the overall market and
    logistics stress levels. The component scores are relative and intended
    for dashboard prioritization.

    Missing components are re-weighted instead of treated as zero.
    """
    market = market_stress_by_mandi()
    logistics = logistics_stress_by_mandi()
    weather = weather_stress()

    market_score = (
        float(market["market_stress_score"].mean())
        if not market.empty
        else None
    )

    logistics_score = (
        float(logistics["logistics_stress_score"].mean())
        if not logistics.empty
        else None
    )

    latest_weather_score = None
    latest_weather_date = None

    if not weather.empty:
        latest = weather.sort_values(
            "weather_date_ist"
        ).iloc[-1]

        if pd.notna(latest["weather_stress_score"]):
            latest_weather_score = float(
                latest["weather_stress_score"]
            )

        latest_weather_date = str(
            latest["weather_date_ist"]
        )

    values = [
        ("market", market_score, 0.40),
        ("logistics", logistics_score, 0.40),
        ("weather", latest_weather_score, 0.20),
    ]

    numerator = sum(
        score * weight
        for _, score, weight in values
        if score is not None
    )

    denominator = sum(
        weight
        for _, score, weight in values
        if score is not None
    )

    overall = (
        _clip_score(numerator / denominator)
        if denominator
        else None
    )

    return {
        "overall_risk_score": (
            None if overall is None else round(overall, 2)
        ),
        "overall_risk": stress_label(overall),
        "market_system_score": (
            None if market_score is None else round(market_score, 2)
        ),
        "logistics_system_score": (
            None
            if logistics_score is None
            else round(logistics_score, 2)
        ),
        "weather_system_score": (
            None
            if latest_weather_score is None
            else round(latest_weather_score, 2)
        ),
        "latest_weather_date": latest_weather_date,
        "method": (
            "Relative percentile scoring. System score uses "
            "40% market, 40% logistics, 20% latest-weather stress; "
            "missing components are re-weighted."
        ),
        "warning": (
            "Scores are prioritization signals relative to the supplied "
            "dataset. They are not probabilities, forecasts, or causal "
            "claims."
        ),
    }


# ---------------------------------------------------------------------
# Compact API for the Streamlit dashboard
# ---------------------------------------------------------------------

def get_dashboard_risk() -> dict:
    """
    Return all objects needed by the dashboard.

    Keeping this as one public entry point makes the UI integration simple.
    """
    return {
        "mandi_risk": mandi_operational_risk(),
        "weather": weather_stress(),
        "system": system_risk_summary(),
        "actions": action_engine(),
    }


# ---------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 72)
    print("DATAFORGE EXPLAINABLE RISK ENGINE")
    print("=" * 72)

    con = get_connection()
    try:
        duplicate_master_ids = con.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT mandi_id
                FROM mandi_master
                GROUP BY mandi_id
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
    finally:
        con.close()

    print(
        f"Duplicate mandi-master IDs detected: {duplicate_master_ids}"
    )
    print("Fact-to-master joins: deduplicated by mandi_id before scoring.")

    result = get_dashboard_risk()

    system = result["system"]

    print("\nSYSTEM RISK")
    print("-" * 72)
    for key, value in system.items():
        print(f"{key}: {value}")

    mandi = result["mandi_risk"]

    print("\nTOP MANDI OPERATIONAL RISKS")
    print("-" * 72)

    if mandi.empty:
        print("No mandi risk observations available.")
    else:
        columns = [
            "mandi_id",
            "mandi_name",
            "district",
            "operational_risk_score",
            "operational_risk",
        ]

        print(
            mandi[columns]
            .head(10)
            .to_string(index=False)
        )

    weather = result["weather"]

    print("\nLATEST WEATHER STRESS")
    print("-" * 72)

    if weather.empty:
        print("No weather observations available.")
    else:
        print(
            weather[
                [
                    "weather_date_ist",
                    "max_rainfall_mm",
                    "rainy_sensor_share_pct",
                    "weather_stress_score",
                    "weather_stress",
                ]
            ]
            .tail(5)
            .to_string(index=False)
        )
