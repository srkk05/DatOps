import pandas as pd
from ingestion import load_raw_data

def show_values(df, column, name, limit=50):
    print(f"\n--- {name}: {column} ---")
    values = (
        df[column]
        .dropna()
        .astype(str)
        .str.strip()
        .value_counts()
    )
    print(f"Unique values: {len(values):,}")
    print(values.head(limit).to_string())

def show_nonstandard_ids(df, column, name):
    values = (
        df[column]
        .dropna()
        .astype(str)
        .str.strip()
    )
    nonstandard = values[
        ~values.str.upper().str.match(r"^MANDI\d{3}$")
    ].value_counts()
    print(f"\n--- {name}: NON-STANDARD {column} ---")
    print(f"Count: {len(nonstandard):,}")
    if len(nonstandard):
        print(nonstandard.head(100).to_string())
    else:
        print("None found")

def analyze_arrivals(df):
    print("\n" + "=" * 80)
    print("ARRIVALS FORENSICS")
    print("=" * 80)
    show_values(df, "crop_name", "Arrivals")
    show_values(df, "unit", "Arrivals")
    show_values(df, "mandi_id", "Arrivals")
    show_nonstandard_ids(df, "mandi_id", "Arrivals")
    print("\nDate examples:")
    print(df["date"].dropna().head(40).to_string(index=False))

def analyze_prices(df):
    print("\n" + "=" * 80)
    print("PRICES FORENSICS")
    print("=" * 80)
    show_values(df, "crop_name", "Prices")
    show_values(df, "mandi_id", "Prices")
    show_nonstandard_ids(df, "mandi_id", "Prices")
    print("\nMin price examples:")
    print(df["min_price"].dropna().head(30).to_string(index=False))
    print("\nMax price examples:")
    print(df["max_price"].dropna().head(30).to_string(index=False))
    print("\nModal price examples:")
    print(df["modal_price"].dropna().head(30).to_string(index=False))
    print("\nMSP examples:")
    print(df["msp"].dropna().head(30).to_string(index=False))

def analyze_weather(df):
    print("\n" + "=" * 80)
    print("WEATHER FORENSICS")
    print("=" * 80)
    show_values(df, "temp_unit", "Weather")
    show_values(df, "rain_unit", "Weather")
    print("\nTimestamp examples:")
    print(df["timestamp"].dropna().head(40).to_string(index=False))
    print("\nTemperature examples:")
    print(df["temperature"].dropna().head(30).to_string(index=False))

def analyze_transport(df):
    print("\n" + "=" * 80)
    print("TRANSPORT FORENSICS")
    print("=" * 80)
    show_values(df, "distance_unit", "Transport")
    show_values(df, "destination_warehouse", "Transport")
    print("\nDeparture time examples:")
    print(df["departure_time"].dropna().head(30).to_string(index=False))
    print("\nArrival time examples:")
    print(df["arrival_time"].dropna().head(30).to_string(index=False))
    print("\nVehicle examples:")
    print(df["vehicle_no"].dropna().head(30).to_string(index=False))

def analyze_master(df):
    print("\n" + "=" * 80)
    print("MANDI MASTER FORENSICS")
    print("=" * 80)
    show_values(df, "mandi_id", "Mandi Master")
    show_values(df, "mandi_type", "Mandi Master")
    print("\nDuplicate mandi IDs:")
    duplicates = df[df["mandi_id"].duplicated(keep=False)]
    print(duplicates.to_string(index=False))

def normalize_mandi_id(value):
    #Convert common mandi ID formats into the canonical MANDI### format.
    if value is None:
        return None
    value = str(value).strip().upper()
    digits = "".join(char for char in value if char.isdigit())
    if not digits:
        return None
    number = int(digits)
    if 1 <= number <= 999:
        return f"MANDI{number:03d}"
    return None

def analyze_relationships(data):
    print("\n" + "=" * 80)
    print("RELATIONSHIP FORENSICS")
    print("=" * 80)
    arrivals = data["arrivals"].copy()
    prices = data["prices"].copy()
    transport = data["transport"].copy()
    master = data["mandi_master"].copy()
    weather = data["weather"].copy()
    # Build the canonical mandi reference set from the master table.
    master_ids = (
        master["mandi_id"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
    )
    master_ids = set(master_ids)
    print("\n--- MANDI MASTER REFERENCE ---")
    print(f"Canonical master IDs: {len(master_ids):,}")
    print(sorted(master_ids))
    arrivals["mandi_id_normalized"] = arrivals["mandi_id"].apply(
        normalize_mandi_id
    )
    arrival_valid = arrivals["mandi_id_normalized"].isin(master_ids)
    print("\n--- ARRIVALS -> MANDI MASTER ---")
    print(f"Total arrival rows: {len(arrivals):,}")
    print(f"Rows matching master: {arrival_valid.sum():,}")
    print(f"Rows NOT matching master: {(~arrival_valid).sum():,}")
    print("\nNormalized arrival ID examples:")
    print(
        arrivals[["mandi_id", "mandi_id_normalized"]]
        .drop_duplicates()
        .head(30)
        .to_string(index=False)
    )
    prices["mandi_id_normalized"] = prices["mandi_id"].apply(
        normalize_mandi_id
    )
    price_valid = prices["mandi_id_normalized"].isin(master_ids)
    print("\n--- PRICES -> MANDI MASTER ---")
    print(f"Total price rows: {len(prices):,}")
    print(f"Rows matching master: {price_valid.sum():,}")
    print(f"Rows NOT matching master: {(~price_valid).sum():,}")
    transport["mandi_id_normalized"] = transport["mandi_id"].apply(
        normalize_mandi_id
    )
    transport_valid = transport["mandi_id_normalized"].isin(master_ids)
    print("\n--- TRANSPORT -> MANDI MASTER ---")
    print(f"Total transport rows: {len(transport):,}")
    print(f"Rows matching master: {transport_valid.sum():,}")
    print(f"Rows NOT matching master: {(~transport_valid).sum():,}")
    arrival_ids = set(
        arrivals["mandi_id_normalized"].dropna().unique()
    )
    price_ids = set(
        prices["mandi_id_normalized"].dropna().unique()
    )
    transport_ids = set(
        transport["mandi_id_normalized"].dropna().unique()
    )
    print("\n--- CROSS-DATA MANDI COVERAGE ---")
    print(f"Master mandis:      {len(master_ids):,}")
    print(f"Arrival mandis:     {len(arrival_ids):,}")
    print(f"Price mandis:       {len(price_ids):,}")
    print(f"Transport mandis:   {len(transport_ids):,}")
    print(f"\nArrival ∩ Price:     {len(arrival_ids & price_ids):,}")
    print(f"Arrival ∩ Transport: {len(arrival_ids & transport_ids):,}")
    print(f"Price ∩ Transport:   {len(price_ids & transport_ids):,}")
    print("\nMandis present in master but absent from arrivals:")
    print(sorted(master_ids - arrival_ids))
    print("\nMandis present in master but absent from prices:")
    print(sorted(master_ids - price_ids))
    print("\nMandis present in master but absent from transport:")
    print(sorted(master_ids - transport_ids))
    print("\n--- ARRIVALS + PRICES JOIN ANALYSIS ---")
    arrivals_dates = pd.to_datetime(
        arrivals["date"],
        errors="coerce",
        dayfirst=False
    )
    prices_dates = pd.to_datetime(
        prices["date"],
        errors="coerce",
        dayfirst=False
    )
    arrivals["date_normalized"] = arrivals_dates.dt.date
    prices["date_normalized"] = prices_dates.dt.date
    arrival_keys = set(
        zip(
            arrivals["mandi_id_normalized"],
            arrivals["date_normalized"],
            arrivals["crop_name"].astype(str).str.strip().str.lower()
        )
    )
    price_keys = set(
        zip(
            prices["mandi_id_normalized"],
            prices["date_normalized"],
            prices["crop_name"].astype(str).str.strip().str.lower()
        )
    )
    common_keys = arrival_keys & price_keys
    print(f"Unique arrival (mandi, date, crop) keys: {len(arrival_keys):,}")
    print(f"Unique price (mandi, date, crop) keys:   {len(price_keys):,}")
    print(f"Common (mandi, date, crop) keys:          {len(common_keys):,}")
    if arrival_keys:
        print(
            f"Arrival keys with price coverage: "
            f"{len(common_keys) / len(arrival_keys) * 100:.2f}%"
        )

    print("\n--- WEATHER CONNECTIVITY ---")
    print("Weather columns:")
    print(list(weather.columns))
    weather_keys = set(weather.columns)
    possible_location_keys = {
        "mandi_id",
        "district",
        "state",
        "latitude",
        "longitude",
        "location"
    }
    found_location_keys = weather_keys & possible_location_keys
    if found_location_keys:
        print(
            "Potential geographic join columns found:",
            sorted(found_location_keys)
        )
    else:
        print(
            "No direct mandi/location join key found in weather data."
        )
    print(
        "\nIMPORTANT: Weather-to-mandi linkage will NOT be invented."
    )
def analyze_price_join_diagnostics(data):
    print("\n" + "=" * 80)
    print("PRICE JOIN DIAGNOSTICS")
    print("=" * 80)
    arrivals = data["arrivals"].copy()
    prices = data["prices"].copy()
    # Normalize mandi IDs without modifying the raw values.
    arrivals["mandi_id_norm"] = arrivals["mandi_id"].apply(
        normalize_mandi_id
    )
    prices["mandi_id_norm"] = prices["mandi_id"].apply(
        normalize_mandi_id
    )
    # Temporary crop normalization for join analysis.
    crop_map = {
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
    arrivals["crop_norm"] = (
        arrivals["crop_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map(crop_map)
    )
    prices["crop_norm"] = (
        prices["crop_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map(crop_map)
    )
    # Normalize dates for diagnostic purposes.
    arrivals["date_norm"] = pd.to_datetime(
        arrivals["date"],
        errors="coerce"
    ).dt.date
    prices["date_norm"] = pd.to_datetime(
        prices["date"],
        errors="coerce"
    ).dt.date
    arrival_mandi = set(
        arrivals["mandi_id_norm"].dropna().unique()
    )
    price_mandi = set(
        prices["mandi_id_norm"].dropna().unique()
    )
    print("\n--- LEVEL 1: MANDI ONLY ---")
    print(
        "Common mandis:",
        len(arrival_mandi & price_mandi)
    )
    print("\n--- LEVEL 2: MANDI + CROP ---")
    arrival_mandi_crop = set(
        zip(
            arrivals["mandi_id_norm"],
            arrivals["crop_norm"]
        )
    )
    price_mandi_crop = set(
        zip(
            prices["mandi_id_norm"],
            prices["crop_norm"]
        )
    )
    common_mandi_crop = (
        arrival_mandi_crop & price_mandi_crop
    )
    print(
        "Arrival (mandi,crop) keys:",
        len(arrival_mandi_crop)
    )
    print(
        "Price (mandi,crop) keys:",
        len(price_mandi_crop)
    )
    print(
        "Common (mandi,crop) keys:",
        len(common_mandi_crop)
    )
    print("\n--- LEVEL 3: MANDI + DATE ---")
    arrival_mandi_date = set(
        zip(
            arrivals["mandi_id_norm"],
            arrivals["date_norm"]
        )
    )
    price_mandi_date = set(
        zip(
            prices["mandi_id_norm"],
            prices["date_norm"]
        )
    )
    common_mandi_date = (
        arrival_mandi_date & price_mandi_date
    )
    print(
        "Arrival (mandi,date) keys:",
        len(arrival_mandi_date)
    )
    print(
        "Price (mandi,date) keys:",
        len(price_mandi_date)
    )
    print(
        "Common (mandi,date) keys:",
        len(common_mandi_date)
    )
    print("\n--- LEVEL 4: MANDI + CROP + DATE ---")
    arrival_full = set(
        zip(
            arrivals["mandi_id_norm"],
            arrivals["crop_norm"],
            arrivals["date_norm"]
        )
    )
    price_full = set(
        zip(
            prices["mandi_id_norm"],
            prices["crop_norm"],
            prices["date_norm"]
        )
    )
    common_full = arrival_full & price_full
    print(
        "Arrival full keys:",
        len(arrival_full)
    )
    print(
        "Price full keys:",
        len(price_full)
    )
    print(
        "Common full keys:",
        len(common_full)
    )
    if arrival_full:
        print(
            "Arrival keys with price coverage:",
            f"{len(common_full) / len(arrival_full) * 100:.2f}%"
        )
    print("\n--- NORMALIZED CROP COVERAGE ---")
    print(
        "Unmapped arrival crops:",
        arrivals["crop_norm"].isna().sum()
    )
    print(
        "Unmapped price crops:",
        prices["crop_norm"].isna().sum()
    )
def analyze_date_alignment(data):
    print("\n" + "=" * 80)
    print("DATE ALIGNMENT FORENSICS")
    print("=" * 80)
    arrivals = data["arrivals"].copy()
    prices = data["prices"].copy()
    # Keep dates as pandas timestamps so missing values remain compatible.
    arrivals["date_norm"] = pd.to_datetime(
        arrivals["date"],
        errors="coerce"
    ).dt.normalize()
    prices["date_norm"] = pd.to_datetime(
        prices["date"],
        errors="coerce"
    ).dt.normalize()
    arrival_dates = set(
        arrivals["date_norm"].dropna().unique()
    )
    price_dates = set(
        prices["date_norm"].dropna().unique()
    )
    common_dates = arrival_dates & price_dates
    print("\n--- DATE RANGES ---")
    print(
        "Arrivals:",
        arrivals["date_norm"].min(),
        "to",
        arrivals["date_norm"].max()
    )
    print(
        "Prices:",
        prices["date_norm"].min(),
        "to",
        prices["date_norm"].max()
    )
    print("\n--- UNIQUE DATE COUNTS ---")
    print("Arrival unique dates:", len(arrival_dates))
    print("Price unique dates:", len(price_dates))
    print("Common dates:", len(common_dates))
    if arrival_dates:
        print(
            "Arrival dates with price coverage:",
            f"{len(common_dates) / len(arrival_dates) * 100:.2f}%"
        )
    print("\n--- ARRIVAL-ONLY DATES ---")
    arrival_only = sorted(arrival_dates - price_dates)
    print("Count:", len(arrival_only))
    print(arrival_only[:50])
    print("\n--- PRICE-ONLY DATES ---")
    price_only = sorted(price_dates - arrival_dates)
    print("Count:", len(price_only))
    print(price_only[:50])

def analyze_mandi_crop_date_gaps(data):
    print("\n" + "=" * 80)
    print("MANDI-CROP DATE GAP FORENSICS")
    print("=" * 80)
    arrivals = data["arrivals"].copy()
    prices = data["prices"].copy()
    arrivals["mandi_id_norm"] = arrivals["mandi_id"].apply(
        normalize_mandi_id
    )
    prices["mandi_id_norm"] = prices["mandi_id"].apply(
        normalize_mandi_id
    )
    crop_map = {
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
    arrivals["crop_norm"] = (
        arrivals["crop_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map(crop_map)
    )
    prices["crop_norm"] = (
        prices["crop_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map(crop_map)
    )
    arrivals["date_norm"] = pd.to_datetime(
        arrivals["date"],
        errors="coerce"
    ).dt.normalize()
    prices["date_norm"] = pd.to_datetime(
        prices["date"],
        errors="coerce"
    ).dt.normalize()
    arrival_groups = (
        arrivals
        .dropna(subset=["mandi_id_norm", "crop_norm", "date_norm"])
        .groupby(["mandi_id_norm", "crop_norm"])["date_norm"]
        .agg(["min", "max", "count"])
        .reset_index()
    )
    price_groups = (
        prices
        .dropna(subset=["mandi_id_norm", "crop_norm", "date_norm"])
        .groupby(["mandi_id_norm", "crop_norm"])["date_norm"]
        .agg(["min", "max", "count"])
        .reset_index()
    )
    comparison = arrival_groups.merge(
        price_groups,
        on=["mandi_id_norm", "crop_norm"],
        how="inner",
        suffixes=("_arrival", "_price")
    )
    comparison["start_gap_days"] = (
        comparison["min_price"] -
        comparison["min_arrival"]
    ).dt.days.abs()
    comparison["end_gap_days"] = (
        comparison["max_price"] -
        comparison["max_arrival"]
    ).dt.days.abs()
    print("\n--- MANDI + CROP COVERAGE ---")
    print("Common mandi-crop combinations:", len(comparison))
    print("\n--- DATE RANGE GAPS ---")
    print(
        "Median start-date gap:",
        comparison["start_gap_days"].median(),
        "days"
    )
    print(
        "Median end-date gap:",
        comparison["end_gap_days"].median(),
        "days"
    )
    print(
        "Maximum start-date gap:",
        comparison["start_gap_days"].max(),
        "days"
    )
    print(
        "Maximum end-date gap:",
        comparison["end_gap_days"].max(),
        "days"
    )
    print("\n--- SAMPLE COMPARISON ---")
    print(
        comparison[
            [
                "mandi_id_norm",
                "crop_norm",
                "min_arrival",
                "max_arrival",
                "min_price",
                "max_price",
                "start_gap_days",
                "end_gap_days",
            ]
        ]
        .sort_values("start_gap_days", ascending=False)
        .head(30)
        .to_string(index=False)
    )
def analyze_price_frequency(data):
    print("\n" + "=" * 80)
    print("PRICE FREQUENCY FORENSICS")
    print("=" * 80)
    prices = data["prices"].copy()
    prices["mandi_id_norm"] = prices["mandi_id"].apply(
        normalize_mandi_id
    )
    crop_map = {
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
    prices["crop_norm"] = (
        prices["crop_name"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map(crop_map)
    )
    prices["date_norm"] = pd.to_datetime(
        prices["date"],
        errors="coerce"
    ).dt.normalize()
    clean_prices = prices.dropna(
        subset=["mandi_id_norm", "crop_norm", "date_norm"]
    )
    grouped = (
        clean_prices
        .groupby(["mandi_id_norm", "crop_norm"])["date_norm"]
        .agg(
            observation_count="count",
            unique_dates="nunique",
            first_date="min",
            last_date="max"
        )
        .reset_index()
    )
    grouped["span_days"] = (
        grouped["last_date"] - grouped["first_date"]
    ).dt.days
    grouped["observations_per_day"] = (
        grouped["unique_dates"] /
        grouped["span_days"].replace(0, pd.NA)
    )
    print("\n--- OVERALL ---")
    print(
        "Mandi-crop combinations:",
        len(grouped)
    )
    print(
        "Median price observations:",
        grouped["observation_count"].median()
    )
    print(
        "Median unique price dates:",
        grouped["unique_dates"].median()
    )
    print(
        "Median date span:",
        grouped["span_days"].median(),
        "days"
    )
    print("\n--- OBSERVATION COUNT DISTRIBUTION ---")
    print(
        grouped["observation_count"]
        .describe()
        .to_string()
    )
    print("\n--- SAMPLE: LOWEST FREQUENCY ---")
    print(
        grouped
        .sort_values("unique_dates")
        .head(20)
        .to_string(index=False)
    )
    print("\n--- SAMPLE: HIGHEST FREQUENCY ---")
    print(
        grouped
        .sort_values("unique_dates", ascending=False)
        .head(20)
        .to_string(index=False)
    )
if __name__ == "__main__":
    data = load_raw_data()

    analyze_arrivals(data["arrivals"])
    analyze_prices(data["prices"])
    analyze_weather(data["weather"])
    analyze_transport(data["transport"])
    analyze_master(data["mandi_master"])
    analyze_relationships(data)
    analyze_price_join_diagnostics(data)
    analyze_date_alignment(data)
    analyze_mandi_crop_date_gaps(data)
    analyze_price_frequency(data)