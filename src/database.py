from pathlib import Path

import duckdb

from ingestion import load_raw_data
from weather_mapping import load_mapping
from cleaning import (
    clean_arrivals,
    clean_prices,
    clean_transport,
    clean_weather,
    clean_mandi_master,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "datops.duckdb"


def build_database():
    """Build the analytical DuckDB database from cleaned DataFrames."""

    print("=" * 80)
    print("BUILDING DUCKDB DATABASE")
    print("=" * 80)

    # Load raw source datasets.
    raw_data = load_raw_data()

    # Apply the same cleaning pipeline used by validation.py.
    arrivals = clean_arrivals(raw_data["arrivals"])
    prices = clean_prices(raw_data["prices"])
    transport = clean_transport(raw_data["transport"])
    weather = clean_weather(raw_data["weather"])
    mandi_master = clean_mandi_master(raw_data["mandi_master"])

    # The competition notes permit a synthetic sensor→district assumption.
    # Apply the tracked deterministic mapping only to known sensors; UNKNOWN
    # rows remain in weather but have no district attribution.
    weather_mapping = load_mapping()
    weather = weather.merge(weather_mapping[["sensor_id", "district"]], on="sensor_id", how="left")

    # Create the database directory if required.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(DB_PATH))

    try:
        # Rebuild tables so the database always reflects the latest
        # cleaning logic.
        for table in [
            "arrivals",
            "prices",
            "transport",
            "weather",
            "mandi_master",
        ]:
            con.execute(f"DROP TABLE IF EXISTS {table}")

        # Register pandas DataFrames with DuckDB.
        con.register("arrivals_df", arrivals)
        con.register("prices_df", prices)
        con.register("transport_df", transport)
        con.register("weather_df", weather)
        con.register("mandi_master_df", mandi_master)

        # Create persistent analytical tables.
        con.execute("""
            CREATE TABLE arrivals AS
            SELECT * FROM arrivals_df
        """)

        con.execute("""
            CREATE TABLE prices AS
            SELECT * FROM prices_df
        """)

        con.execute("""
            CREATE TABLE transport AS
            SELECT * FROM transport_df
        """)

        con.execute("""
            CREATE TABLE weather AS
            SELECT * FROM weather_df
        """)

        con.execute("""
            CREATE TABLE mandi_master AS
            SELECT * FROM mandi_master_df
        """)

        print()
        print("=" * 80)
        print("DATABASE BUILT SUCCESSFULLY")
        print("=" * 80)
        print(f"Database: {DB_PATH}")
        print()

        for table in [
            "mandi_master",
            "arrivals",
            "prices",
            "transport",
            "weather",
        ]:
            count = con.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"{table:15} {count:>8,} rows")

    finally:
        con.close()


if __name__ == "__main__":
    build_database()