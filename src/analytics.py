"""DatOps analytical helpers.

All functions read the validated DuckDB layer.  The arrival-shock detector is
an adaptive, coverage-aware comparison of recent arrival intensity against the
immediately preceding window.  It is a descriptive anomaly signal, not a
forecast.
"""
from __future__ import annotations

from pathlib import Path
import sys

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "datops.duckdb"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def get_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"DuckDB database not found: {DB_PATH}. Run `python src/database.py` first."
        )
    return duckdb.connect(str(DB_PATH), read_only=True)


def transit_threshold() -> pd.DataFrame:
    """Return the empirical P90 transit benchmark used across the dashboard."""
    con = get_connection()
    try:
        return con.execute(
            """
            SELECT
                quantile_cont(transit_hours, 0.90) AS p90_transit_hours,
                COUNT(*) AS valid_transport_records
            FROM transport
            WHERE transit_hours IS NOT NULL
              AND transit_hours >= 0
            """
        ).fetchdf()
    finally:
        con.close()


def warehouse_logistics() -> pd.DataFrame:
    """Summarize transport performance by destination warehouse.

    Delay uses the same empirical P90 transit benchmark as the risk engine.
    This measures inbound trip activity, not shipment tonnage: the transport
    source has no shipment-quantity field.
    """
    con = get_connection()
    try:
        return con.execute(
            """
            WITH valid AS (
                SELECT destination_warehouse, transit_hours, distance_km
                FROM transport
                WHERE transit_status = 'VALID'
                  AND transit_hours IS NOT NULL
                  AND transit_hours >= 0
                  AND destination_warehouse IS NOT NULL
                  AND TRIM(destination_warehouse) <> ''
            ), threshold AS (
                SELECT quantile_cont(transit_hours, 0.90) AS p90_hours
                FROM valid
            )
            SELECT
                TRIM(v.destination_warehouse) AS destination_warehouse,
                COUNT(*) AS trips,
                ROUND(AVG(v.transit_hours), 2) AS avg_transit_hours,
                ROUND(MEDIAN(v.transit_hours), 2) AS median_transit_hours,
                ROUND(AVG(v.distance_km), 2) AS avg_distance_km,
                SUM(CASE WHEN v.transit_hours > t.p90_hours THEN 1 ELSE 0 END) AS delayed_trips,
                ROUND(100.0 * AVG(CASE WHEN v.transit_hours > t.p90_hours THEN 1.0 ELSE 0.0 END), 2) AS delay_rate_pct
            FROM valid v CROSS JOIN threshold t
            GROUP BY TRIM(v.destination_warehouse)
            ORDER BY delay_rate_pct DESC, avg_transit_hours DESC
            """
        ).fetchdf()
    finally:
        con.close()


def route_logistics(min_trips: int = 10) -> pd.DataFrame:
    """Summarize mandi-to-warehouse routes and their delay performance."""
    min_trips = max(1, int(min_trips))
    con = get_connection()
    try:
        return con.execute(
            f"""
            WITH valid AS (
                SELECT mandi_id, destination_warehouse, transit_hours, distance_km
                FROM transport
                WHERE transit_status = 'VALID'
                  AND transit_hours IS NOT NULL
                  AND transit_hours >= 0
                  AND mandi_id IS NOT NULL
                  AND destination_warehouse IS NOT NULL
                  AND TRIM(destination_warehouse) <> ''
            ), threshold AS (
                SELECT quantile_cont(transit_hours, 0.90) AS p90_hours
                FROM valid
            ), master AS (
                SELECT mandi_id,
                       MAX(mandi_name) AS mandi_name,
                       MAX(district) AS district,
                       MAX(state) AS state
                FROM mandi_master
                GROUP BY mandi_id
            )
            SELECT
                v.mandi_id,
                COALESCE(m.mandi_name, v.mandi_id) AS mandi_name,
                m.district,
                m.state,
                TRIM(v.destination_warehouse) AS destination_warehouse,
                COUNT(*) AS trips,
                ROUND(AVG(v.transit_hours), 2) AS avg_transit_hours,
                ROUND(MEDIAN(v.transit_hours), 2) AS median_transit_hours,
                ROUND(AVG(v.distance_km), 2) AS avg_distance_km,
                SUM(CASE WHEN v.transit_hours > t.p90_hours THEN 1 ELSE 0 END) AS delayed_trips,
                ROUND(100.0 * AVG(CASE WHEN v.transit_hours > t.p90_hours THEN 1.0 ELSE 0.0 END), 2) AS delay_rate_pct
            FROM valid v
            CROSS JOIN threshold t
            LEFT JOIN master m ON v.mandi_id = m.mandi_id
            GROUP BY v.mandi_id, m.mandi_name, m.district, m.state, TRIM(v.destination_warehouse)
            HAVING COUNT(*) >= {min_trips}
            ORDER BY delay_rate_pct DESC, delayed_trips DESC, avg_transit_hours DESC
            """
        ).fetchdf()
    finally:
        con.close()


def weather_by_district(days: int = 90) -> pd.DataFrame:
    """Aggregate valid weather by the tracked synthetic sensor→district map."""
    days = max(1, min(int(days), 365))
    con = get_connection()
    try:
        return con.execute(
            f"""
            WITH daily AS (
                SELECT district, weather_date_ist,
                       AVG(temperature_c) AS avg_temperature_c,
                       AVG(CASE WHEN rainfall_status='VALID' THEN rainfall_mm END) AS avg_rainfall_mm,
                       MAX(CASE WHEN rainfall_status='VALID' THEN rainfall_mm END) AS max_rainfall_mm,
                       COUNT(DISTINCT CASE WHEN rainfall_status='VALID' THEN sensor_id END) AS reporting_sensors,
                       AVG(humidity_percent) AS avg_humidity
                FROM weather
                WHERE district IS NOT NULL
                  AND weather_date_ist IS NOT NULL
                  AND weather_date_ist >= (SELECT MAX(weather_date_ist) FROM weather) - INTERVAL {days} DAY
                GROUP BY district, weather_date_ist
            )
            SELECT district,
                   ROUND(AVG(avg_temperature_c),2) AS avg_temperature_c,
                   ROUND(SUM(avg_rainfall_mm),2) AS cumulative_avg_rainfall_mm,
                   ROUND(MAX(max_rainfall_mm),2) AS peak_rainfall_mm,
                   ROUND(AVG(avg_humidity),2) AS avg_humidity,
                   SUM(reporting_sensors) AS sensor_day_reports,
                   COUNT(*) AS observed_days
            FROM daily
            GROUP BY district
            ORDER BY cumulative_avg_rainfall_mm DESC
            """
        ).fetchdf()
    finally:
        con.close()


def weather_arrival_correlation_by_district(days: int = 365) -> pd.DataFrame:
    """Descriptive district-level rainfall/arrival correlations.

    Weather attribution uses the tracked synthetic sensor→district mapping.
    Results require same district and IST calendar date; they do not imply causality.
    """
    days = max(1, min(int(days), 365))
    con = get_connection()
    try:
        return con.execute(
            f"""
            WITH weather_daily AS (
                SELECT district, weather_date_ist,
                       AVG(CASE WHEN rainfall_status='VALID' THEN rainfall_mm END) avg_rainfall_mm
                FROM weather
                WHERE district IS NOT NULL AND weather_date_ist IS NOT NULL
                  AND weather_date_ist >= (SELECT MAX(weather_date_ist) FROM weather) - INTERVAL {days} DAY
                GROUP BY district, weather_date_ist
            ), arrival_daily AS (
                SELECT m.district, CAST(a.date AS DATE) arrival_date,
                       SUM(a.arrival_quantity_qtl) arrivals_qtl
                FROM arrivals a
                JOIN (SELECT mandi_id, MAX(district) district FROM mandi_master GROUP BY mandi_id) m
                  ON a.mandi_id=m.mandi_id
                WHERE a.quantity_status='VALID' AND a.date IS NOT NULL AND m.district IS NOT NULL
                GROUP BY m.district, CAST(a.date AS DATE)
            )
            SELECT w.district,
                   COUNT(*) overlap_days,
                   ROUND(corr(w.avg_rainfall_mm, a.arrivals_qtl), 4) rainfall_arrival_corr
            FROM weather_daily w
            JOIN arrival_daily a
              ON LOWER(TRIM(w.district))=LOWER(TRIM(a.district))
             AND CAST(w.weather_date_ist AS DATE)=a.arrival_date
            WHERE w.avg_rainfall_mm IS NOT NULL
            GROUP BY w.district
            HAVING COUNT(*) >= 2
            ORDER BY rainfall_arrival_corr
            """
        ).fetchdf()
    finally:
        con.close()


def arrival_shock_by_mandi(
    window_days: int = 30,
    min_observed_days: int = 3,
) -> pd.DataFrame:
    """Detect recent mandi-level arrival surges/drops.

    Method:
      * Aggregate only VALID standardized arrivals by mandi and calendar day.
      * Compare the latest ``window_days`` against the immediately preceding
        window of equal length.
      * Normalize each window by observed arrival days so sparse coverage does
        not automatically look like a shock.
      * Require a minimum number of observed days in both windows.

    ``shock_pct`` is the percent change in average observed-day arrivals.
    Positive = surge; negative = drop.
    """
    window_days = max(7, min(int(window_days), 90))
    min_observed_days = max(2, min(int(min_observed_days), window_days))

    con = get_connection()
    try:
        query = f"""
        WITH daily AS (
            SELECT
                mandi_id,
                CAST(date AS DATE) AS arrival_date,
                SUM(arrival_quantity_qtl) AS arrivals_qtl
            FROM arrivals
            WHERE quantity_status = 'VALID'
              AND mandi_id IS NOT NULL
              AND date IS NOT NULL
            GROUP BY mandi_id, CAST(date AS DATE)
        ),
        bounds AS (
            SELECT MAX(arrival_date) AS max_date FROM daily
        ),
        windows AS (
            SELECT
                d.mandi_id,
                SUM(CASE
                    WHEN d.arrival_date > b.max_date - INTERVAL {window_days - 1} DAY
                     AND d.arrival_date <= b.max_date
                    THEN d.arrivals_qtl ELSE 0 END) AS recent_total_qtl,
                COUNT(DISTINCT CASE
                    WHEN d.arrival_date > b.max_date - INTERVAL {window_days - 1} DAY
                     AND d.arrival_date <= b.max_date
                    THEN d.arrival_date END) AS recent_observed_days,
                SUM(CASE
                    WHEN d.arrival_date > b.max_date - INTERVAL {2 * window_days - 1} DAY
                     AND d.arrival_date <= b.max_date - INTERVAL {window_days} DAY
                    THEN d.arrivals_qtl ELSE 0 END) AS baseline_total_qtl,
                COUNT(DISTINCT CASE
                    WHEN d.arrival_date > b.max_date - INTERVAL {2 * window_days - 1} DAY
                     AND d.arrival_date <= b.max_date - INTERVAL {window_days} DAY
                    THEN d.arrival_date END) AS baseline_observed_days
            FROM daily d
            CROSS JOIN bounds b
            GROUP BY d.mandi_id
        )
        SELECT
            w.mandi_id,
            COALESCE(m.mandi_name, w.mandi_id) AS mandi_name,
            m.district,
            m.state,
            CAST(b.max_date AS DATE) AS latest_arrival_date,
            {window_days} AS window_days,
            w.recent_total_qtl,
            w.recent_observed_days,
            w.baseline_total_qtl,
            w.baseline_observed_days,
            CASE WHEN w.recent_observed_days > 0
                 THEN w.recent_total_qtl / w.recent_observed_days END AS recent_avg_daily_qtl,
            CASE WHEN w.baseline_observed_days > 0
                 THEN w.baseline_total_qtl / w.baseline_observed_days END AS baseline_avg_daily_qtl
        FROM windows w
        CROSS JOIN bounds b
        LEFT JOIN (
            SELECT mandi_id,
                   MAX(mandi_name) AS mandi_name,
                   MAX(district) AS district,
                   MAX(state) AS state
            FROM mandi_master
            GROUP BY mandi_id
        ) m ON w.mandi_id = m.mandi_id
        WHERE w.recent_observed_days >= {min_observed_days}
          AND w.baseline_observed_days >= {min_observed_days}
          AND w.baseline_total_qtl > 0
        ORDER BY w.mandi_id
        """
        df = con.execute(query).fetchdf()
    finally:
        con.close()

    if df.empty:
        return df

    df["shock_pct"] = (
        (df["recent_avg_daily_qtl"] - df["baseline_avg_daily_qtl"])
        / df["baseline_avg_daily_qtl"]
        * 100
    )
    df["abs_shock_pct"] = df["shock_pct"].abs()
    df["shock_direction"] = df["shock_pct"].apply(
        lambda x: "SURGE" if x >= 20 else ("DROP" if x <= -20 else "STABLE")
    )
    df["coverage_pct"] = (
        (df["recent_observed_days"] + df["baseline_observed_days"])
        / (2 * window_days)
        * 100
    )
    # Relative anomaly magnitude among eligible mandis.
    if len(df) == 1:
        df["shock_score"] = 50.0
    else:
        df["shock_score"] = df["abs_shock_pct"].rank(method="average", pct=True) * 100
    df["shock_score"] = df["shock_score"].round(2)
    df["shock_confidence"] = df["coverage_pct"].apply(
        lambda x: "HIGH" if x >= 40 else ("MEDIUM" if x >= 25 else "LOW")
    )
    return df.sort_values("abs_shock_pct", ascending=False).reset_index(drop=True)


def arrival_shock_by_mandi_crop(
    window_days: int = 30,
    min_observed_days: int = 3,
) -> pd.DataFrame:
    """Same detector at mandi × canonical-crop level for drill-downs."""
    window_days = max(7, min(int(window_days), 90))
    min_observed_days = max(2, min(int(min_observed_days), window_days))
    con = get_connection()
    try:
        df = con.execute(
            f"""
            WITH daily AS (
                SELECT mandi_id, crop_name, CAST(date AS DATE) arrival_date,
                       SUM(arrival_quantity_qtl) arrivals_qtl
                FROM arrivals
                WHERE quantity_status='VALID' AND mandi_id IS NOT NULL AND date IS NOT NULL
                GROUP BY mandi_id, crop_name, CAST(date AS DATE)
            ), bounds AS (SELECT MAX(arrival_date) max_date FROM daily),
            agg AS (
                SELECT d.mandi_id, d.crop_name,
                    SUM(CASE WHEN d.arrival_date > b.max_date - INTERVAL {window_days-1} DAY
                              AND d.arrival_date <= b.max_date THEN d.arrivals_qtl ELSE 0 END) recent_total,
                    COUNT(DISTINCT CASE WHEN d.arrival_date > b.max_date - INTERVAL {window_days-1} DAY
                              AND d.arrival_date <= b.max_date THEN d.arrival_date END) recent_days,
                    SUM(CASE WHEN d.arrival_date > b.max_date - INTERVAL {2*window_days-1} DAY
                              AND d.arrival_date <= b.max_date - INTERVAL {window_days} DAY THEN d.arrivals_qtl ELSE 0 END) baseline_total,
                    COUNT(DISTINCT CASE WHEN d.arrival_date > b.max_date - INTERVAL {2*window_days-1} DAY
                              AND d.arrival_date <= b.max_date - INTERVAL {window_days} DAY THEN d.arrival_date END) baseline_days
                FROM daily d CROSS JOIN bounds b
                GROUP BY d.mandi_id, d.crop_name
            )
            SELECT a.*, CAST(b.max_date AS DATE) latest_arrival_date
            FROM agg a CROSS JOIN bounds b
            WHERE recent_days >= {min_observed_days}
              AND baseline_days >= {min_observed_days}
              AND baseline_total > 0
            """
        ).fetchdf()
    finally:
        con.close()
    if df.empty:
        return df
    df["recent_avg_daily_qtl"] = df["recent_total"] / df["recent_days"]
    df["baseline_avg_daily_qtl"] = df["baseline_total"] / df["baseline_days"]
    df["shock_pct"] = (df["recent_avg_daily_qtl"] - df["baseline_avg_daily_qtl"]) / df["baseline_avg_daily_qtl"] * 100
    df["shock_direction"] = df["shock_pct"].apply(lambda x: "SURGE" if x >= 20 else ("DROP" if x <= -20 else "STABLE"))
    return df.sort_values("shock_pct").reset_index(drop=True)


if __name__ == "__main__":
    print("DatOps analytics smoke test")
    print(transit_threshold().to_string(index=False))
    shocks = arrival_shock_by_mandi()
    print(f"Eligible mandi shocks: {len(shocks):,}")
    if not shocks.empty:
        print(shocks.head(10).to_string(index=False))
