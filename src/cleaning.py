import re

import pandas as pd

from ingestion import load_raw_data


# ---------------------------------------------------------------------------
# Canonical mappings
# ---------------------------------------------------------------------------

CROP_MAP = {
    "sugarcane": "sugarcane",
    "ganna": "sugarcane",
    "ganne": "sugarcane",
    "गन्ना": "sugarcane",

    "cotton": "cotton",
    "kapas": "cotton",
    "narma": "cotton",
    "कपास": "cotton",

    "mustard": "mustard",
    "sarson": "mustard",
    "sarso": "mustard",
    "सरसों": "mustard",

    "wheat": "wheat",
    "gehun": "wheat",
    "kanak": "wheat",
    "गेहूं": "wheat",

    "corn": "maize",
    "maize": "maize",
    "makka": "maize",
    "makki": "maize",
    "मक्का": "maize",

    "rice": "rice",
    "paddy": "rice",
    "chawal": "rice",
    "dhaan": "rice",
    "धान": "rice",
    "चावल": "rice",
    "basmati": "rice",
}


UNIT_TO_KG = {
    "kg": 1,
    "kgs": 1,
    "kilo": 1,
    "q": 100,
    "qtl": 100,
    "quintal": 100,
    "quintals": 100,
    "mt": 1000,
    "t": 1000,
    "tonne": 1000,
    "tonnes": 1000,
}


TEMP_UNIT_MAP = {
    "c": "C",
    "°c": "C",
    "celsius": "C",
    "f": "F",
    "°f": "F",
    "fahrenheit": "F",
}


RAIN_UNIT_MAP = {
    "mm": "mm",
    "millimeters": "mm",
    "inch": "inch",
    "inches": "inch",
    "in": "inch",
}


# ---------------------------------------------------------------------------
# Basic normalization functions
# ---------------------------------------------------------------------------

def normalize_mandi_id(value):
    """Convert common mandi ID formats into canonical MANDI### format."""

    if pd.isna(value):
        return None

    value = str(value).strip().upper()

    digits = "".join(char for char in value if char.isdigit())

    if not digits:
        return None

    number = int(digits)

    if 1 <= number <= 999:
        return f"MANDI{number:03d}"

    return None


def normalize_crop_name(value):
    """Map multilingual and inconsistent crop names to canonical names."""

    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    return CROP_MAP.get(value)


def parse_date(value):
    """Parse known source date formats without ambiguous inference."""

    if pd.isna(value):
        return pd.NaT

    value = str(value).strip()

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%m.%d.%Y",
        "%d-%b-%Y",
        "%d-%b-%y",
    ]

    for fmt in formats:
        try:
            return pd.to_datetime(value, format=fmt)
        except (ValueError, TypeError):
            continue

    return pd.to_datetime(value, errors="coerce")


def parse_numeric(value):
    """Extract a numeric value from messy currency/formatted strings."""

    if pd.isna(value):
        return None

    value = str(value).strip()

    # Remove currency prefixes such as Rs., INR and ₹.
    value = re.sub(r"(?i)\brs\.?\s*", "", value)
    value = re.sub(r"(?i)\binr\s*", "", value)
    value = value.replace("₹", "")

    # Remove thousands separators and common suffixes.
    value = value.replace(",", "")
    value = value.replace("/-", "")
    value = value.strip()

    match = re.search(r"-?\d+(?:\.\d+)?", value)

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def normalize_unit(value):
    """Map source quantity units to canonical unit names."""

    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    return value if value in UNIT_TO_KG else None


def convert_quantity_to_kg(quantity, unit):
    """Convert arrival quantity to kilograms."""

    if pd.isna(quantity) or pd.isna(unit):
        return None

    multiplier = UNIT_TO_KG.get(str(unit).strip().lower())

    if multiplier is None:
        return None

    return float(quantity) * multiplier


# ---------------------------------------------------------------------------
# Arrival cleaning
# ---------------------------------------------------------------------------

def clean_arrivals(df):
    """Clean and standardize the mandi arrivals fact table."""

    df = df.copy()

    df["mandi_id"] = df["mandi_id"].apply(normalize_mandi_id)

    df["crop_name"] = df["crop_name"].apply(normalize_crop_name)

    df["date"] = df["date"].apply(parse_date)

    df["unit"] = df["unit"].apply(normalize_unit)

    df["arrival_quantity"] = pd.to_numeric(
        df["arrival_quantity"],
        errors="coerce",
    )

    df["arrival_quantity_kg"] = df.apply(
        lambda row: convert_quantity_to_kg(
            row["arrival_quantity"],
            row["unit"],
        ),
        axis=1,
    )

    # Keep source problems visible instead of silently modifying them.
    df["quantity_status"] = "VALID"

    df.loc[
        df["arrival_quantity"].isna(),
        "quantity_status",
    ] = "MISSING"

    df.loc[
        df["arrival_quantity"].notna()
        & (df["arrival_quantity"] < 0),
        "quantity_status",
    ] = "INVALID_NEGATIVE"

    df.loc[
        df["arrival_quantity"].notna()
        & df["unit"].isna(),
        "quantity_status",
    ] = "INVALID_UNIT"

    return df


# ---------------------------------------------------------------------------
# Price cleaning
# ---------------------------------------------------------------------------

def clean_prices(df):
    """Clean and standardize the mandi price and MSP fact table."""

    df = df.copy()

    df["mandi_id"] = df["mandi_id"].apply(normalize_mandi_id)

    df["crop_name"] = df["crop_name"].apply(normalize_crop_name)

    df["date"] = df["date"].apply(parse_date)

    for column in [
        "min_price",
        "max_price",
        "modal_price",
        "msp",
    ]:
        df[column] = df[column].apply(parse_numeric)

    df["price_status"] = "VALID"

    complete_prices = df[
        [
            "min_price",
            "modal_price",
            "max_price",
        ]
    ].notna().all(axis=1)

    invalid_order = complete_prices & ~(
        (df["min_price"] <= df["modal_price"])
        & (df["modal_price"] <= df["max_price"])
    )

    df.loc[
        invalid_order,
        "price_status",
    ] = "INVALID_ORDER"

    return df


# ---------------------------------------------------------------------------
# Transport cleaning
# ---------------------------------------------------------------------------

def clean_transport(df):
    """Clean transport records and standardize distance units."""

    df = df.copy()

    df["mandi_id"] = df["mandi_id"].apply(normalize_mandi_id)

    df["departure_time"] = pd.to_datetime(
        df["departure_time"],
        errors="coerce",
    )

    df["arrival_time"] = pd.to_datetime(
        df["arrival_time"],
        errors="coerce",
    )

    df["transit_hours"] = pd.to_numeric(
        df["transit_hours"],
        errors="coerce",
    )

    df["distance"] = pd.to_numeric(
        df["distance"],
        errors="coerce",
    )

    df["distance_unit"] = (
        df["distance_unit"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    # Convert miles to kilometres while preserving the original distance.
    df["distance_km"] = df["distance"]

    miles_mask = df["distance_unit"].isin(
        ["mile", "miles", "mi"]
    )

    df.loc[
        miles_mask,
        "distance_km",
    ] = df.loc[
        miles_mask,
        "distance"
    ] * 1.609344

    df["transit_status"] = "VALID"

    df.loc[
        df["transit_hours"].isna(),
        "transit_status",
    ] = "MISSING"

    df.loc[
        df["transit_hours"].notna()
        & (df["transit_hours"] < 0),
        "transit_status",
    ] = "INVALID_NEGATIVE"

    return df


# ---------------------------------------------------------------------------
# Weather cleaning
# ---------------------------------------------------------------------------

def normalize_temp_unit(value):
    """Normalize temperature units to C or F."""

    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    return TEMP_UNIT_MAP.get(value)


def normalize_rain_unit(value):
    """Normalize rainfall units to mm or inch."""

    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    return RAIN_UNIT_MAP.get(value)

def parse_datetime_with_timezone(value):
    """Parse mixed weather timestamps and normalize them to UTC."""

    if pd.isna(value):
        return pd.NaT

    value = str(value).strip()

    # Explicit timezone formats.
    timezone_formats = [
        "%Y-%m-%d %H:%M:%S %Z",
        "%Y-%m-%d %H:%M %Z",
        "%d/%m/%Y %H:%M:%S %Z",
        "%d/%m/%Y %H:%M %Z",
        "%d-%m-%Y %H:%M:%S %Z",
        "%d-%m-%Y %H:%M %Z",
    ]

    for fmt in timezone_formats:
        try:
            timestamp = pd.to_datetime(
                value,
                format=fmt,
            )

            # Convert timezone-aware timestamps to UTC.
            if timestamp.tzinfo is not None:
                return timestamp.tz_convert("UTC")

            return timestamp.tz_localize("UTC")

        except (ValueError, TypeError):
            continue

    # Explicitly handle UTC / IST offsets.
    normalized = (
        value.replace(" UTC", "+00:00")
        .replace(" IST", "+05:30")
    )

    offset_formats = [
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M%z",
        "%d/%m/%Y %H:%M:%S%z",
        "%d/%m/%Y %H:%M%z",
        "%d-%m-%Y %H:%M:%S%z",
        "%d-%m-%Y %H:%M%z",
    ]

    for fmt in offset_formats:
        try:
            timestamp = pd.to_datetime(
                normalized,
                format=fmt,
            )

            return timestamp.tz_convert("UTC")

        except (ValueError, TypeError):
            continue

    # Formats without an explicit timezone.
    naive_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
    ]

    for fmt in naive_formats:
        try:
            timestamp = pd.to_datetime(
                value,
                format=fmt,
            )

            return timestamp.tz_localize("UTC")

        except (ValueError, TypeError):
            continue

    return pd.NaT

def clean_weather(df):
    """Clean weather sensor data and convert measurements to standard units."""

    df = df.copy()

    df["timestamp"] = df["timestamp"].apply(parse_datetime_with_timezone)

    df["temperature"] = pd.to_numeric(
        df["temperature"],
        errors="coerce",
    )

    df["rainfall"] = pd.to_numeric(
        df["rainfall"],
        errors="coerce",
    )

    df["humidity_percent"] = pd.to_numeric(
        df["humidity_percent"],
        errors="coerce",
    )

    df["temp_unit"] = df["temp_unit"].apply(
        normalize_temp_unit
    )

    df["rain_unit"] = df["rain_unit"].apply(
        normalize_rain_unit
    )

    # Preserve the original measurements and create canonical columns.
    df["temperature_c"] = df["temperature"]

    fahrenheit_mask = df["temp_unit"] == "F"

    df.loc[
        fahrenheit_mask,
        "temperature_c",
    ] = (
        df.loc[
            fahrenheit_mask,
            "temperature"
        ] - 32
    ) * 5 / 9

    df["rainfall_mm"] = df["rainfall"]

    inch_mask = df["rain_unit"] == "inch"

    df.loc[
        inch_mask,
        "rainfall_mm",
    ] = (
        df.loc[
            inch_mask,
            "rainfall"
        ] * 25.4
    )

    return df


# ---------------------------------------------------------------------------
# Mandi master cleaning
# ---------------------------------------------------------------------------

def clean_mandi_master(df):
    """Clean the mandi master dimension."""

    df = df.copy()

    df["mandi_id"] = df["mandi_id"].apply(
        normalize_mandi_id
    )

    df["mandi_name"] = (
        df["mandi_name"]
        .astype("string")
        .str.strip()
    )

    df["district"] = (
        df["district"]
        .astype("string")
        .str.strip()
    )

    df["state"] = (
        df["state"]
        .astype("string")
        .str.strip()
    )

    df["mandi_type"] = (
        df["mandi_type"]
        .astype("string")
        .str.strip()
    )

    df["total_area_acres"] = pd.to_numeric(
        df["total_area_acres"],
        errors="coerce",
    )

    return df


# ---------------------------------------------------------------------------
# Price anomaly investigation
# ---------------------------------------------------------------------------

def analyze_price_anomalies(raw_prices, cleaned_prices):
    """Check for obviously broken numeric price conversions."""

    print("\n" + "=" * 80)
    print("PRICE ANOMALY INVESTIGATION")
    print("=" * 80)

    result = raw_prices.copy()

    for column in [
        "min_price",
        "max_price",
        "modal_price",
        "msp",
    ]:
        result[f"{column}_clean"] = cleaned_prices[column].values

    for column in [
        "min_price",
        "max_price",
        "modal_price",
        "msp",
    ]:
        print(f"\n--- {column.upper()} ---")

        suspicious = result[
            result[f"{column}_clean"].notna()
            & (result[f"{column}_clean"] < 100)
        ]

        print(
            "Values below 100:",
            len(suspicious)
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    data = load_raw_data()

    arrivals = clean_arrivals(
        data["arrivals"]
    )

    prices = clean_prices(
        data["prices"]
    )

    transport = clean_transport(
        data["transport"]
    )

    weather = clean_weather(
        data["weather"]
    )

    mandi_master = clean_mandi_master(
        data["mandi_master"]
    )

    analyze_price_anomalies(
        data["prices"],
        prices,
    )

    print("\n" + "=" * 80)
    print("CLEANING PREVIEW")
    print("=" * 80)

    print("\n--- ARRIVALS ---")

    print(
        arrivals[
            [
                "arrival_id",
                "date",
                "mandi_id",
                "crop_name",
                "arrival_quantity",
                "unit",
                "arrival_quantity_kg",
                "quantity_status",
                "farmer_count",
            ]
        ]
        .head()
        .to_string(index=False)
    )

    print("\n--- PRICES ---")

    print(
        prices[
            [
                "record_id",
                "date",
                "mandi_id",
                "crop_name",
                "min_price",
                "max_price",
                "modal_price",
                "msp",
                "price_status",
            ]
        ]
        .head()
        .to_string(index=False)
    )

    print("\n--- TRANSPORT ---")

    print(
        transport[
            [
                "trip_id",
                "mandi_id",
                "transit_hours",
                "distance",
                "distance_unit",
                "distance_km",
                "transit_status",
            ]
        ]
        .head()
        .to_string(index=False)
    )

    print("\n--- WEATHER ---")

    print(
        weather[
            [
                "sensor_id",
                "timestamp",
                "temperature",
                "temp_unit",
                "temperature_c",
                "rainfall",
                "rain_unit",
                "rainfall_mm",
                "humidity_percent",
            ]
        ]
        .head()
        .to_string(index=False)
    )

    print("\n--- CLEANING COUNTS ---")

    print(
        "Arrivals rows:",
        len(arrivals)
    )

    print(
        "Prices rows:",
        len(prices)
    )

    print(
        "Transport rows:",
        len(transport)
    )

    print(
        "Weather rows:",
        len(weather)
    )

    print(
        "Mandi master rows:",
        len(mandi_master)
    )

    print(
        "Unresolved arrival mandi IDs:",
        arrivals["mandi_id"].isna().sum()
    )

    print(
        "Unresolved arrival crops:",
        arrivals["crop_name"].isna().sum()
    )

    print(
        "Invalid arrival dates:",
        arrivals["date"].isna().sum()
    )

    print(
        "Unresolved price mandi IDs:",
        prices["mandi_id"].isna().sum()
    )

    print(
        "Unresolved price crops:",
        prices["crop_name"].isna().sum()
    )

    print(
        "Invalid price dates:",
        prices["date"].isna().sum()
    )

    print("\n--- ARRIVAL QUANTITY CHECK ---")

    print(
        "Missing arrival quantities:",
        arrivals["arrival_quantity"].isna().sum()
    )

    print(
        "Negative arrival quantities:",
        (
            arrivals["arrival_quantity"] < 0
        ).sum()
    )

    print(
        "Missing arrival units:",
        arrivals["unit"].isna().sum()
    )

    print(
        "Missing converted quantities:",
        arrivals["arrival_quantity_kg"].isna().sum()
    )

    print("\n--- ARRIVAL STATUS ---")

    print(
        arrivals["quantity_status"]
        .value_counts()
        .to_string()
    )

    print("\n--- PRICE STATUS ---")

    print(
        prices["price_status"]
        .value_counts()
        .to_string()
    )

    print("\n--- TRANSPORT STATUS ---")

    print(
        transport["transit_status"]
        .value_counts()
        .to_string()
    )

    print("\n--- PRICE NUMERIC CHECK ---")

    for column in [
        "min_price",
        "max_price",
        "modal_price",
        "msp",
    ]:
        print(
            f"{column}:",
            prices[column].notna().sum(),
            "numeric values"
        )


if __name__ == "__main__":
    main()