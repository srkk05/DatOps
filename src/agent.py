"""DataForge AgriQuery: safe natural-language analytics over DuckDB."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "datops.duckdb"

try:
    from src.risk_engine import get_dashboard_risk
except ImportError:  # allows `python src/agent.py` as well as package import
    from risk_engine import get_dashboard_risk


@dataclass
class QueryPlan:
    intent: str
    sql: str
    title: str
    explanation: str
    chart: str = "table"
    params: tuple[Any, ...] = ()
    data_override: pd.DataFrame | None = None


ALLOWED_INTENTS = {
    "top_mandis", "crop_arrivals", "below_msp", "transit_delay",
    "mandi_risk", "weather", "daily_arrivals", "price_summary",
    "stress_matrix", "warehouse_logistics", "route_logistics", "summary",
}


def get_connection() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DuckDB database not found: {DB_PATH}")
    return duckdb.connect(str(DB_PATH), read_only=True)


def _clean_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def _extract_limit(q: str, default: int = 5) -> int:
    m = re.search(r"\b(?:top|first)\s+(\d+)\b", q)
    return max(1, min(int(m.group(1)), 25)) if m else default


def _extract_mandi_id(q: str) -> str | None:
    m = re.search(r"\bmandi\s*0*(\d{1,3})\b", q, re.I)
    return f"MANDI{int(m.group(1)):03d}" if m else None


def _extract_crop(q: str) -> str | None:
    for crop in ("wheat", "rice", "maize", "cotton", "mustard", "sugarcane"):
        if re.search(rf"\b{re.escape(crop)}\b", q):
            return crop
    return None


def _extract_days(q: str, default: int = 30) -> int:
    m = re.search(r"\b(?:last|past)\s+(\d+)\s+days?\b", q)
    if m:
        return max(1, min(int(m.group(1)), 365))
    m = re.search(r"\b(?:last|past)\s+(\d+)\s+months?\b", q)
    if m:
        return max(1, min(int(m.group(1)) * 30, 365))
    return default


def _extract_warehouse(q: str) -> str | None:
    m = re.search(r"\b(wh-(?:north|south|east|west|central)|export-terminal)\b", q, re.I)
    return m.group(1).upper() if m else None


def _resolve_location(text: str) -> tuple[str | None, str | None]:
    """Resolve a place against the curated master without fabricating geography.

    Returns (mandi_id, district). Exact mandi name wins. If there is no exact
    mandi name, an exact district match is used and the result is aggregated
    across that district's mandis.
    """
    token = text.strip().lower()
    if not token:
        return None, None
    with get_connection() as con:
        exact = con.execute(
            """
            SELECT mandi_id FROM (
                SELECT mandi_id, LOWER(TRIM(mandi_name)) AS mandi_name,
                       ROW_NUMBER() OVER (PARTITION BY mandi_id ORDER BY mandi_id) rn
                FROM mandi_master
            )
            WHERE rn = 1 AND mandi_name = ?
            LIMIT 1
            """, [token]
        ).fetchone()
        if exact:
            return str(exact[0]), None
        district = con.execute(
            "SELECT DISTINCT LOWER(TRIM(district)) FROM mandi_master WHERE LOWER(TRIM(district)) = ? LIMIT 1",
            [token],
        ).fetchone()
        if district:
            return None, token
    return None, None


def _resolve_query_location(q: str) -> tuple[str | None, str | None, str]:
    """Find a likely mandi/district phrase, currently prioritising known districts."""
    districts = {
        "agra", "ambala", "amritsar", "bareilly", "bathinda", "fatehabad",
        "ferozepur", "hisar", "jalandhar", "karnal", "kurukshetra", "ludhiana",
        "meerut", "moga", "muzaffarnagar", "patiala", "saharanpur", "sirsa",
    }
    for d in sorted(districts, key=len, reverse=True):
        if re.search(rf"\b{re.escape(d)}\b", q):
            mid, district = _resolve_location(d)
            return mid, district, d
    return None, None, ""


def _plan_deterministic(question: str) -> QueryPlan:
    q = _clean_question(question)
    limit = _extract_limit(q)
    crop = _extract_crop(q)
    mandi_id = _extract_mandi_id(q)
    days = _extract_days(q)
    resolved_mandi = resolved_district = None
    location = ""
    if crop and any(k in q for k in ("mandi", "district", " in ", " at ", " from ")):
        resolved_mandi, resolved_district, location = _resolve_query_location(q)

    # 1. Signature combined stress question.
    if ("both" in q and ("price pressure" in q or "below msp" in q)
            and ("slow logistics" in q or "transit" in q)) or "stress matrix" in q:
        sql = """
        WITH master AS (
            SELECT mandi_id, ANY_VALUE(mandi_name) mandi_name,
                   ANY_VALUE(district) district, ANY_VALUE(state) state
            FROM mandi_master GROUP BY mandi_id
        ), arrivals AS (
            SELECT mandi_id, SUM(arrival_quantity_qtl) arrivals_qtl
            FROM arrivals
            WHERE quantity_status = 'VALID'
            GROUP BY mandi_id
        ), market AS (
            SELECT mandi_id,
                   100.0 * AVG(CASE WHEN modal_price < msp THEN 1.0 ELSE 0.0 END) below_msp_rate
            FROM prices
            WHERE modal_price IS NOT NULL AND msp IS NOT NULL
            GROUP BY mandi_id
        ), logistics AS (
            SELECT mandi_id, AVG(transit_hours) avg_transit_hours,
                   100.0 * AVG(CASE WHEN transit_hours > p90.p90_hours THEN 1.0 ELSE 0.0 END) delay_rate
            FROM transport
            CROSS JOIN (
                SELECT quantile_cont(transit_hours, 0.90) p90_hours
                FROM transport WHERE transit_status = 'VALID' AND transit_hours IS NOT NULL AND transit_hours >= 0
            ) p90
            WHERE transit_status = 'VALID' AND transit_hours IS NOT NULL AND transit_hours >= 0
            GROUP BY mandi_id
        )
        SELECT m.mandi_id, m.mandi_name, m.district, m.state,
               a.arrivals_qtl, mk.below_msp_rate, lg.avg_transit_hours, lg.delay_rate
        FROM master m
        LEFT JOIN arrivals a ON a.mandi_id = m.mandi_id
        LEFT JOIN market mk ON mk.mandi_id = m.mandi_id
        LEFT JOIN logistics lg ON lg.mandi_id = m.mandi_id
        WHERE a.arrivals_qtl IS NOT NULL
          AND mk.below_msp_rate IS NOT NULL
          AND lg.avg_transit_hours IS NOT NULL
        ORDER BY (mk.below_msp_rate + lg.avg_transit_hours) DESC
        """
        return QueryPlan("stress_matrix", sql,
                         "Supply-chain stress matrix",
                         "Combines valid arrival volume, below-MSP pressure and logistics speed. Dashed quadrants use filtered medians; this is a relative prioritization view.",
                         "stress_matrix")

    # 2. Specific mandi risk — use the canonical risk engine, not a dummy SQL row.
    if mandi_id and any(k in q for k in ("risk", "priority", "stress", "why")):
        risk = get_dashboard_risk().get("mandi_risk", pd.DataFrame()).copy()
        if not risk.empty:
            risk["mandi_id"] = risk["mandi_id"].astype(str)
            row = risk[risk["mandi_id"].eq(mandi_id)].copy()
            if not row.empty:
                return QueryPlan(
                    "mandi_risk", "-- risk_engine: database-derived explainable score",
                    f"Risk evidence for {mandi_id}",
                    "Explainable operational priority combining market and logistics stress. The score is relative to the supplied dataset, not a failure probability or forecast.",
                    "indicator", data_override=row,
                )

    # 3. Official-style query: wheat + Amritsar + last 30 days + MSP reference.
    if crop and location and ("arrival" in q or "trend" in q) and ("msp" in q or "price" in q):
        location_clause = "a.mandi_id = ?" if resolved_mandi else "LOWER(TRIM(m.district)) = ?"
        params: tuple[Any, ...] = (crop, location if not resolved_mandi else resolved_mandi)
        sql = f"""
        WITH latest AS (
            SELECT MAX(date) max_date FROM arrivals WHERE date IS NOT NULL
        ), daily AS (
            SELECT CAST(a.date AS DATE) arrival_date,
                   ROUND(SUM(a.arrival_quantity_qtl), 2) arrivals_qtl
            FROM arrivals a
            LEFT JOIN (SELECT mandi_id, ANY_VALUE(district) district FROM mandi_master GROUP BY mandi_id) m
              ON a.mandi_id = m.mandi_id
            CROSS JOIN latest
            WHERE a.quantity_status = 'VALID'
              AND a.crop_name = ?
              AND {location_clause}
              AND a.date >= latest.max_date - INTERVAL 30 DAY
            GROUP BY CAST(a.date AS DATE)
        ), msp AS (
            SELECT crop_name, ROUND(AVG(msp),2) avg_msp
            FROM prices
            WHERE crop_name = ? AND msp IS NOT NULL
            GROUP BY crop_name
        )
        SELECT d.arrival_date, d.arrivals_qtl, m.avg_msp
        FROM daily d CROSS JOIN msp m
        ORDER BY d.arrival_date
        """
        params = (crop, location if not resolved_mandi else resolved_mandi, crop)
        resolution = (f"{location.title()} was resolved to an exact mandi." if resolved_mandi
                      else f"No exact mandi named {location.title()} exists in the supplied master, so {location.title()} was interpreted as the district filter.")
        return QueryPlan("daily_arrivals", sql,
                         f"{crop.title()} arrivals — {location.title()} — last 30 days",
                         f"{resolution} MSP is shown as a reference line from available price observations; missing daily price observations are not fabricated.",
                         "line_msp", params=params)

    if (re.search(r"\btop\s+\d+\s+mandis?\b", q)
            or any(k in q for k in ("top mandi", "top mandis", "highest arrival", "most arrivals"))):
        sql = f"""
        WITH master AS (
            SELECT mandi_id, ANY_VALUE(mandi_name) mandi_name, ANY_VALUE(district) district, ANY_VALUE(state) state
            FROM mandi_master GROUP BY mandi_id
        )
        SELECT a.mandi_id, m.mandi_name, m.district, m.state,
               ROUND(SUM(a.arrival_quantity_qtl),2) arrivals_qtl
        FROM arrivals a LEFT JOIN master m ON a.mandi_id = m.mandi_id
        WHERE a.quantity_status='VALID' AND a.mandi_id IS NOT NULL
        GROUP BY a.mandi_id, m.mandi_name, m.district, m.state
        ORDER BY arrivals_qtl DESC LIMIT {limit}
        """
        return QueryPlan("top_mandis", sql, f"Top {limit} mandis by arrivals",
                         "Ranked using valid standardized arrival quantities in quintals; the master dimension is deduplicated before joining.", "bar")

    if any(k in q for k in ("arrivals by crop", "crop arrivals", "total arrivals by crop", "arrival distribution")):
        sql = """
        SELECT crop_name, ROUND(SUM(arrival_quantity_qtl),2) arrivals_qtl
        FROM arrivals WHERE quantity_status='VALID' AND crop_name IS NOT NULL
        GROUP BY crop_name ORDER BY arrivals_qtl DESC
        """
        return QueryPlan("crop_arrivals", sql, "Arrivals by crop",
                         "Only valid standardized quantities are included.", "bar")

    if any(k in q for k in ("below msp", "price below", "prices below")):
        crop_clause = "AND p.crop_name = ?" if crop else ""
        params = (crop,) if crop else ()
        sql = f"""
        SELECT p.mandi_id, p.crop_name AS crop,
               ROUND(AVG(p.modal_price),2) AS avg_modal_price,
               ROUND(AVG(p.msp),2) AS avg_msp,
               ROUND(100.0 * AVG(CASE WHEN p.modal_price < p.msp THEN 1.0 ELSE 0.0 END),2) AS below_msp_rate,
               COUNT(*) AS observations
        FROM prices p
        WHERE p.mandi_id IS NOT NULL AND p.modal_price IS NOT NULL AND p.msp IS NOT NULL
          {crop_clause}
        GROUP BY p.mandi_id, p.crop_name
        HAVING AVG(CASE WHEN p.modal_price < p.msp THEN 1.0 ELSE 0.0 END) > 0
        ORDER BY below_msp_rate DESC, observations DESC
        LIMIT {max(limit, 15) if not crop else limit}
        """
        return QueryPlan("below_msp", sql, f"Mandis below MSP" + (f" — {crop.title()}" if crop else ""),
                         "Summarized by mandi and crop so the result is decision-ready rather than a dump of individual observations.", "table", params)

    # District-level weather is available through the tracked synthetic
    # sensor→district mapping. Keep the attribution caveat in the response.
    if ("district" in q and any(k in q for k in ("weather", "rainfall", "rain", "temperature"))):
        sql = f"""
        WITH daily AS (
            SELECT district, weather_date_ist,
                   AVG(temperature_c) avg_temperature_c,
                   AVG(CASE WHEN rainfall_status='VALID' THEN rainfall_mm END) avg_rainfall_mm,
                   MAX(CASE WHEN rainfall_status='VALID' THEN rainfall_mm END) peak_rainfall_mm,
                   COUNT(DISTINCT CASE WHEN rainfall_status='VALID' THEN sensor_id END) reporting_sensors
            FROM weather
            WHERE district IS NOT NULL AND weather_date_ist IS NOT NULL
              AND weather_date_ist >= (SELECT MAX(weather_date_ist) FROM weather) - INTERVAL {days} DAY
            GROUP BY district, weather_date_ist
        )
        SELECT district,
               ROUND(AVG(avg_temperature_c),2) avg_temperature_c,
               ROUND(SUM(avg_rainfall_mm),2) cumulative_avg_rainfall_mm,
               ROUND(MAX(peak_rainfall_mm),2) peak_rainfall_mm,
               SUM(reporting_sensors) sensor_day_reports,
               COUNT(*) observed_days
        FROM daily
        GROUP BY district
        ORDER BY cumulative_avg_rainfall_mm DESC
        """
        return QueryPlan("weather", sql, f"District weather — last {days} available days",
                         "District attribution uses the tracked synthetic sensor→district mapping permitted by the dataset notes. Multiple sensors can map to a district and UNKNOWN sensors remain unattributed. Cumulative rainfall is the sum of daily district-average rainfall, not a physical district total.", "bar")

    warehouse = _extract_warehouse(q)

    # Destination-warehouse performance. "Volume" is intentionally represented
    # as inbound trip activity because transport contains no shipment quantity.
    if any(k in q for k in ("warehouse", "wh-north", "wh-south", "wh-east", "wh-west", "wh-central", "export-terminal")) and not any(k in q for k in ("route", "from mandi", "mandi to", "between mandi")):
        warehouse_clause = "AND UPPER(TRIM(destination_warehouse)) = ?" if warehouse else ""
        params = (warehouse,) if warehouse else ()
        sql = f"""
        WITH valid AS (
            SELECT destination_warehouse, transit_hours, distance_km
            FROM transport
            WHERE transit_status='VALID' AND transit_hours IS NOT NULL AND transit_hours >= 0
              AND destination_warehouse IS NOT NULL AND TRIM(destination_warehouse) <> ''
              {warehouse_clause}
        ), p90 AS (
            SELECT quantile_cont(transit_hours,0.90) p90_hours FROM valid
        )
        SELECT TRIM(v.destination_warehouse) destination_warehouse,
               COUNT(*) trips,
               ROUND(AVG(v.transit_hours),2) avg_transit_hours,
               ROUND(MEDIAN(v.transit_hours),2) median_transit_hours,
               ROUND(AVG(v.distance_km),2) avg_distance_km,
               SUM(CASE WHEN v.transit_hours > p90.p90_hours THEN 1 ELSE 0 END) delayed_trips,
               ROUND(100.0*AVG(CASE WHEN v.transit_hours > p90.p90_hours THEN 1.0 ELSE 0.0 END),2) delay_rate_pct
        FROM valid v CROSS JOIN p90
        GROUP BY TRIM(v.destination_warehouse)
        ORDER BY delay_rate_pct DESC, avg_transit_hours DESC
        """
        title = f"Warehouse logistics — {warehouse}" if warehouse else "Warehouse logistics performance"
        explanation = ("Shows inbound trip activity by destination warehouse. 'Trips' is used instead of tonnage because the supplied transport records do not contain shipment quantity. Delay uses the empirical P90 transit threshold." )
        return QueryPlan("warehouse_logistics", sql, title, explanation, "bar", params)

    # Mandi-to-warehouse route performance, including delay frequency.
    if any(k in q for k in ("route", "from mandi", "mandi to", "between mandi", "delay frequency")) and (warehouse or "warehouse" in q):
        warehouse_clause = "AND UPPER(TRIM(t.destination_warehouse)) = ?" if warehouse else ""
        params = (warehouse,) if warehouse else ()
        sql = f"""
        WITH p90 AS (
            SELECT quantile_cont(transit_hours,0.90) p90_hours
            FROM transport
            WHERE transit_status='VALID' AND transit_hours IS NOT NULL AND transit_hours >= 0
        ), master AS (
            SELECT mandi_id, ANY_VALUE(mandi_name) mandi_name, ANY_VALUE(district) district, ANY_VALUE(state) state
            FROM mandi_master GROUP BY mandi_id
        )
        SELECT t.mandi_id, m.mandi_name, m.district, m.state,
               TRIM(t.destination_warehouse) destination_warehouse,
               COUNT(*) trips,
               ROUND(AVG(t.transit_hours),2) avg_transit_hours,
               ROUND(MEDIAN(t.transit_hours),2) median_transit_hours,
               ROUND(AVG(t.distance_km),2) avg_distance_km,
               SUM(CASE WHEN t.transit_hours > p90.p90_hours THEN 1 ELSE 0 END) delayed_trips,
               ROUND(100.0*AVG(CASE WHEN t.transit_hours > p90.p90_hours THEN 1.0 ELSE 0.0 END),2) delay_rate_pct
        FROM transport t CROSS JOIN p90
        LEFT JOIN master m ON t.mandi_id=m.mandi_id
        WHERE t.transit_status='VALID' AND t.transit_hours IS NOT NULL AND t.transit_hours >= 0
          AND t.destination_warehouse IS NOT NULL AND TRIM(t.destination_warehouse) <> ''
          {warehouse_clause}
        GROUP BY t.mandi_id, m.mandi_name, m.district, m.state, TRIM(t.destination_warehouse)
        HAVING COUNT(*) >= 10
        ORDER BY delay_rate_pct DESC, delayed_trips DESC, avg_transit_hours DESC
        LIMIT {max(limit, 15)}
        """
        title = f"Mandi → {warehouse} route performance" if warehouse else "Mandi-to-warehouse route watchlist"
        return QueryPlan("route_logistics", sql, title,
                         "Routes are ranked by delay rate and delay frequency using the empirical P90 transit benchmark. This is descriptive operational evidence, not an SLA or forecast.", "bar", params)

    if any(k in q for k in ("transit", "delay", "delayed", "logistics")):
        sql = f"""
        WITH p90 AS (
            SELECT quantile_cont(transit_hours,0.90) p90_hours FROM transport
            WHERE transit_status='VALID' AND transit_hours IS NOT NULL AND transit_hours >= 0
        )
        SELECT t.mandi_id, ANY_VALUE(m.mandi_name) mandi_name,
               ROUND(AVG(t.transit_hours),2) avg_transit_hours,
               ROUND(100.0*AVG(CASE WHEN t.transit_hours > p90.p90_hours THEN 1.0 ELSE 0.0 END),2) delay_rate,
               COUNT(*) trips
        FROM transport t CROSS JOIN p90
        LEFT JOIN (SELECT mandi_id, ANY_VALUE(mandi_name) mandi_name FROM mandi_master GROUP BY mandi_id) m
          ON t.mandi_id=m.mandi_id
        WHERE t.transit_status='VALID' AND t.transit_hours IS NOT NULL AND t.transit_hours >= 0
        GROUP BY t.mandi_id ORDER BY delay_rate DESC, avg_transit_hours DESC LIMIT {limit}
        """
        return QueryPlan("transit_delay", sql, "Transport delay watchlist",
                         "Delay uses the empirical dataset P90 threshold, not an external SLA.", "bar")

    if any(k in q for k in ("weather", "rainfall", "rain", "temperature")):
        sql = f"""
        SELECT weather_date_ist,
               ROUND(AVG(temperature_c),2) avg_temperature_c,
               ROUND(AVG(CASE WHEN rainfall_status='VALID' THEN rainfall_mm END),2) avg_rainfall_mm,
               ROUND(MAX(CASE WHEN rainfall_status='VALID' THEN rainfall_mm END),2) max_rainfall_mm,
               COUNT(DISTINCT CASE WHEN rainfall_status='VALID' AND rainfall_mm > 0 THEN sensor_id END) rainy_sensor_count
        FROM weather
        WHERE weather_date_ist IS NOT NULL
        GROUP BY weather_date_ist
        ORDER BY weather_date_ist DESC LIMIT {days}
        """
        return QueryPlan("weather", sql, f"Weather — last {days} available days",
                         "Weather is aggregated by IST date because the source does not provide a defensible sensor-to-mandi mapping.", "line")

    if (any(k in q for k in ("daily arrivals", "arrival trend", "trend"))
            or (crop is not None and "arrival" in q and re.search(r"\b(?:last|past)\s+\d+\s+days?\b", q))):
        crop_clause = "AND crop_name = ?" if crop else ""
        params = (crop,) if crop else ()
        sql = f"""
        WITH latest AS (SELECT MAX(date) max_date FROM arrivals WHERE date IS NOT NULL)
        SELECT CAST(date AS DATE) arrival_date, ROUND(SUM(arrival_quantity_qtl),2) arrivals_qtl
        FROM arrivals, latest
        WHERE quantity_status='VALID' {crop_clause}
          AND date >= latest.max_date - INTERVAL {days} DAY
        GROUP BY CAST(date AS DATE) ORDER BY arrival_date
        """
        return QueryPlan("daily_arrivals", sql, f"Daily {crop.title()} arrivals" if crop else "Daily arrivals",
                         "Daily trend based on valid standardized arrival quantities.", "line", params)

    if ("price" in q or "msp" in q) and crop:
        sql = """
        SELECT crop_name, ROUND(AVG(modal_price),2) avg_modal_price,
               ROUND(AVG(msp),2) avg_msp,
               ROUND(100.0*AVG(CASE WHEN modal_price < msp THEN 1.0 ELSE 0.0 END),2) below_msp_rate,
               ROUND(AVG(modal_price-msp),2) avg_gap, COUNT(*) observations
        FROM prices WHERE crop_name=? AND modal_price IS NOT NULL AND msp IS NOT NULL
        GROUP BY crop_name
        """
        return QueryPlan("price_summary", sql, f"{crop.title()} price vs MSP",
                         "Average modal price is compared with the available MSP; below-MSP rate is a pressure signal.", "price_comparison", (crop,))

    sql = """
    SELECT 'valid_arrivals_qtl' AS metric, ROUND(SUM(arrival_quantity_qtl),2) AS metric_value FROM arrivals WHERE quantity_status='VALID'
    UNION ALL SELECT 'price_observations', COUNT(*) AS metric_value FROM prices
    UNION ALL SELECT 'valid_transport_records', COUNT(*) AS metric_value FROM transport WHERE transit_status='VALID' AND transit_hours IS NOT NULL
    """
    return QueryPlan("summary", sql, "DataForge snapshot",
                     "The question did not map confidently to a supported analytical view, so the agent returned a safe dataset snapshot.", "table")


def _validate_sql(sql: str) -> None:
    normalized = re.sub(r"\s+", " ", sql.strip().lower())
    if normalized.startswith("--"):
        return
    if not (normalized.startswith("with ") or normalized.startswith("select ")):
        raise ValueError("Only read-only SELECT queries are permitted.")
    forbidden = ["insert ", "update ", "delete ", "drop ", "alter ", "create ", "attach ", "copy ", "pragma ", "install ", "load ", ";"]
    if any(token in normalized for token in forbidden):
        raise ValueError("Unsafe SQL was blocked.")


def _summary(intent: str, df: pd.DataFrame, plan: QueryPlan) -> str:
    if df.empty:
        return f"{plan.explanation} No matching observations were found."
    if intent == "top_mandis" and "arrivals_qtl" in df:
        r = df.iloc[0]
        return f"{r.get('mandi_name', r.get('mandi_id'))} ranks first with {float(r['arrivals_qtl']):,.0f} Qtl of valid arrivals. {plan.explanation}"
    if intent == "price_summary" and "avg_modal_price" in df:
        r = df.iloc[0]
        return f"Average modal price is ₹{float(r['avg_modal_price']):,.0f} versus MSP ₹{float(r['avg_msp']):,.0f}; {float(r['below_msp_rate']):.1f}% of available observations are below MSP. {plan.explanation}"
    if intent == "mandi_risk" and "operational_risk_score" in df:
        r = df.iloc[0]
        return f"{r['mandi_id']} is {r['operational_risk']} at {float(r['operational_risk_score']):.1f}/100. Market stress is {float(r['market_stress_score']):.1f} and logistics stress is {float(r['logistics_stress_score']):.1f}. {plan.explanation}"
    if intent == "daily_arrivals" and "arrivals_qtl" in df:
        return f"The query returned {len(df)} daily observations. {plan.explanation}"
    if intent == "stress_matrix":
        return f"{len(df)} mandis have valid arrival, market-pressure and logistics signals for the combined stress view. {plan.explanation}"
    return f"Returned {len(df):,} observations. {plan.explanation}"


def plan_question(question: str) -> QueryPlan:
    question = question.strip()
    if not question:
        raise ValueError("Please enter a question.")
    return _plan_deterministic(question)


def run_question(question: str) -> dict[str, Any]:
    plan = plan_question(question)
    if plan.data_override is not None:
        result = plan.data_override.copy()
    else:
        _validate_sql(plan.sql)
        with get_connection() as con:
            result = con.execute(plan.sql, plan.params).df()

    summary = _summary(plan.intent, result, plan)
    return {
        "question": question,
        "intent": plan.intent,
        "title": plan.title,
        "explanation": plan.explanation,
        "summary": summary,
        "chart": plan.chart,
        "chart_type": plan.chart,
        "sql": plan.sql.strip(),
        "rows": result,
        "data": result,
        "row_count": len(result),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ask the DataForge AgriQuery agent.")
    parser.add_argument("question", nargs="+", help="Natural-language question")
    args = parser.parse_args()
    output = run_question(" ".join(args.question))
    print(json.dumps({"intent": output["intent"], "title": output["title"], "summary": output["summary"], "row_count": output["row_count"]}, indent=2))
    print(output["data"].to_string(index=False))
