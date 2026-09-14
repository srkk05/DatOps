import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cleaning import (  # noqa: E402
    clean_arrivals,
    clean_prices,
    clean_transport,
    clean_weather,
    clean_mandi_master,
    convert_quantity_to_kg,
    normalize_crop_name,
    normalize_mandi_id,
)


def test_normalization_helpers():
    assert normalize_mandi_id("mandi_001") == "MANDI001"
    assert normalize_mandi_id("M-7") == "MANDI007"
    assert normalize_crop_name("गेहूं") == "wheat"
    assert normalize_crop_name("Basmati") == "rice"


def test_quantity_conversion():
    assert convert_quantity_to_kg(1, "qtl") == 100.0
    assert convert_quantity_to_kg(1, "tonne") == 1000.0
    assert convert_quantity_to_kg(500, "kg") == 500.0


def test_clean_arrivals_adds_standard_quantity_and_status():
    raw = pd.DataFrame(
        {
            "arrival_id": ["A1", "A2", "A3"],
            "date": ["2026-01-01", "01-02-2026", "2026-01-03"],
            "mandi_id": ["M001", "mandi_002", "M-003"],
            "crop_name": ["Wheat", "गेहूं", "Rice"],
            "variety": ["x", "y", "z"],
            "arrival_quantity": [10, -5, 2],
            "unit": ["Qtl", "kg", "tonne"],
            "farmer_count": [1, 2, 3],
        }
    )

    cleaned = clean_arrivals(raw)

    assert cleaned["mandi_id"].tolist() == ["MANDI001", "MANDI002", "MANDI003"]
    assert cleaned["crop_name"].tolist() == ["wheat", "wheat", "rice"]
    assert cleaned["arrival_quantity_kg"].tolist() == [1000.0, -5.0, 2000.0]
    assert cleaned["quantity_status"].tolist() == [
        "VALID",
        "INVALID_NEGATIVE",
        "VALID",
    ]


def test_clean_prices_parses_currency_and_checks_order():
    raw = pd.DataFrame(
        {
            "record_id": ["P1", "P2"],
            "date": ["2026-01-01", "2026-01-02"],
            "mandi_id": ["M001", "M002"],
            "crop_name": ["Wheat", "Rice"],
            "district": ["X", "Y"],
            "min_price": ["₹2,000", "100"],
            "modal_price": ["Rs. 2,100", "90"],
            "max_price": ["INR 2,200", "120"],
            "msp": ["2,275", "100"],
        }
    )

    cleaned = clean_prices(raw)

    assert cleaned.loc[0, "modal_price"] == 2100.0
    assert cleaned.loc[0, "msp"] == 2275.0
    assert cleaned.loc[0, "price_status"] == "VALID"
    assert cleaned.loc[1, "price_status"] == "INVALID_ORDER"


def test_clean_transport_flags_negative_transit():
    raw = pd.DataFrame(
        {
            "trip_id": ["T1", "T2"],
            "mandi_id": ["M001", "M002"],
            "vehicle_no": ["PB 10 AB 1234", "HR-26-C-9999"],
            "driver_id": ["D1", "D2"],
            "departure_time": ["2026-01-01 08:00", "2026-01-01 09:00"],
            "arrival_time": ["2026-01-01 12:00", "2026-01-01 10:00"],
            "distance": [100, 10],
            "distance_unit": ["KM", "Miles"],
            "destination_warehouse": ["WH-North", "WH-South"],
            "transit_hours": ["4 hrs", -1],
        }
    )

    cleaned = clean_transport(raw)

    assert cleaned.loc[0, "transit_status"] == "VALID"
    assert cleaned.loc[1, "transit_status"] == "INVALID_NEGATIVE"
    assert round(cleaned.loc[1, "distance_km"], 6) == round(10 * 1.609344, 6)
    assert cleaned.loc[0, "vehicle_no_normalized"] == "PB-10-AB-1234"


def test_clean_weather_recovers_embedded_temperature_units():
    raw = pd.DataFrame(
        {
            "sensor_id": ["S1", "S2"],
            "timestamp": ["2026-01-01T00:00:00Z", "2026-01-01 06:00:00"],
            "temperature": ["68°F", "25°C"],
            "temp_unit": [None, None],
            "rainfall": ["1 inch", "-2 mm"],
            "rain_unit": ["inch", "mm"],
            "humidity_percent": [70, 80],
        }
    )

    cleaned = clean_weather(raw)

    assert round(cleaned.loc[0, "temperature_c"], 6) == round((68 - 32) * 5 / 9, 6)
    assert cleaned.loc[1, "temperature_c"] == 25.0
    assert round(cleaned.loc[0, "rainfall_mm"], 6) == 25.4
    assert cleaned.loc[1, "rainfall_status"] != "VALID"


def test_clean_mandi_master_preserves_rows_and_normalizes_ids():
    raw = pd.DataFrame(
        {
            "mandi_id": ["M001", "mandi_002"],
            "mandi_name": [" Test A ", "Test B"],
            "district": [" X ", "Y"],
            "state": ["Punjab", "Haryana"],
            "mandi_type": ["APMC", "APMC"],
            "total_area_acres": ["10", "20"],
        }
    )

    cleaned = clean_mandi_master(raw)

    assert cleaned["mandi_id"].tolist() == ["MANDI001", "MANDI002"]
    assert cleaned["mandi_name"].tolist() == ["Test A", "Test B"]
    assert cleaned["total_area_acres"].tolist() == [10, 20]
