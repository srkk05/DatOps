"""Deterministic synthetic weather sensor -> district mapping.

The competition notes explicitly allow a 1:1 sensor-location assumption for
weather-to-district attribution. The workbook itself contains no district
field, so this mapping is an analytical assumption, not source geography.
Multiple sensors can map to one district; UNKNOWN is intentionally unmapped.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "data" / "weather_sensor_district_map.csv"


def build_sensor_district_map(sensor_ids, districts) -> pd.DataFrame:
    sensors = sorted({str(x).strip().upper() for x in sensor_ids if pd.notna(x) and str(x).strip().upper() != "UNKNOWN"})
    districts = sorted({str(x).strip().lower() for x in districts if pd.notna(x) and str(x).strip()})
    if not sensors or not districts:
        return pd.DataFrame(columns=["sensor_id", "district", "mapping_method", "mapping_version"])
    rows = []
    for i, sensor in enumerate(sensors):
        rows.append({
            "sensor_id": sensor,
            "district": districts[i % len(districts)],
            "mapping_method": "synthetic_round_robin_per_dataset_notes",
            "mapping_version": "v1",
        })
    return pd.DataFrame(rows)


def save_mapping(sensor_ids, districts) -> pd.DataFrame:
    mapping = build_sensor_district_map(sensor_ids, districts)
    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(MAP_PATH, index=False)
    return mapping


def load_mapping() -> pd.DataFrame:
    if not MAP_PATH.exists():
        raise FileNotFoundError(f"Weather mapping not found: {MAP_PATH}")
    return pd.read_csv(MAP_PATH)


if __name__ == "__main__":
    weather = pd.read_excel(ROOT / "data" / "raw" / "track3_weather_sensors.xlsx")
    master = pd.read_csv(ROOT / "data" / "raw" / "track3_mandi_master.csv")
    mapping = save_mapping(weather["sensor_id"], master["district"])
    print(mapping.to_string(index=False))
    print(f"Saved {len(mapping)} sensor mappings to {MAP_PATH}")
