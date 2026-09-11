import pandas as pd

from ingestion import load_raw_data
from cleaning import (
    clean_arrivals,
    clean_prices,
    normalize_mandi_id,
    normalize_crop_name,
)


def print_section(title):
    """Print a consistent section header for the validation report."""

    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def validate_duplicates(data):
    """Check duplicate rows in each raw dataset."""

    print_section("1. DUPLICATE VALIDATION")

    datasets = {
        "Arrivals": data["arrivals"],
        "Prices": data["prices"],
        "Transport": data["transport"],
        "Weather": data["weather"],
        "Mandi Master": data["mandi_master"],
    }

    for name, df in datasets.items():
        print(f"{name}: {df.duplicated().sum():,} duplicate rows")


def validate_missing_values(data):
    """Report important missing-value counts."""

    print_section("2. MISSING VALUE VALIDATION")

    datasets = {
        "Arrivals": data["arrivals"],
        "Prices": data["prices"],
        "Transport": data["transport"],
        "Weather": data["weather"],
        "Mandi Master": data["mandi_master"],
    }

    for name, df in datasets.items():
        print(f"\n--- {name} ---")

        missing = df.isna().sum()
        missing = missing[missing > 0]

        if missing.empty:
            print("No missing values")
        else:
            print(missing.to_string())


def validate_arrivals(arrivals):
    """Validate the cleaned arrivals dataset."""

    print_section("3. ARRIVALS VALIDATION")

    print("Rows:", len(arrivals))
    print("Canonical mandi IDs:", arrivals["mandi_id"].notna().sum())
    print("Canonical crops:", arrivals["crop_name"].notna().sum())
    print("Valid dates:", arrivals["date"].notna().sum())

    negative = (arrivals["arrival_quantity"] < 0).sum()
    zero = (arrivals["arrival_quantity"] == 0).sum()
    missing_quantity = arrivals["arrival_quantity"].isna().sum()
    missing_unit = arrivals["unit"].isna().sum()

    print("Negative quantities:", negative)
    print("Zero quantities:", zero)
    print("Missing quantities:", missing_quantity)
    print("Missing units:", missing_unit)

    valid_converted = (
        arrivals["arrival_quantity_kg"].notna()
        & (arrivals["arrival_quantity_kg"] >= 0)
    )

    print("Valid converted quantities:", valid_converted.sum())

    print("\nUnique canonical crops:")
    print(
        sorted(
            arrivals["crop_name"]
            .dropna()
            .unique()
            .tolist()
        )
    )


def validate_prices(prices):
    """Validate numeric and logical price relationships."""

    print_section("4. PRICE VALIDATION")

    print("Rows:", len(prices))

    for column in [
        "min_price",
        "modal_price",
        "max_price",
        "msp",
    ]:
        print(
            f"{column}:",
            prices[column].notna().sum(),
            "numeric values"
        )

    print("\nNegative prices:")

    for column in [
        "min_price",
        "modal_price",
        "max_price",
        "msp",
    ]:
        negative = (prices[column] < 0).sum()
        print(f"{column}: {negative}")

    # Validate the expected price ordering where all three values exist.
    complete = prices[
        [
            "min_price",
            "modal_price",
            "max_price",
        ]
    ].notna().all(axis=1)

    invalid_order = prices.loc[
        complete
        & ~(
            (prices["min_price"] <= prices["modal_price"])
            & (prices["modal_price"] <= prices["max_price"])
        )
    ]

    print("\nInvalid min <= modal <= max rows:", len(invalid_order))

    if len(invalid_order):
        print(
            invalid_order[
                [
                    "record_id",
                    "min_price",
                    "modal_price",
                    "max_price",
                ]
            ]
            .head(20)
            .to_string(index=False)
        )

    invalid_msp = prices[
        prices["msp"].notna()
        & (prices["msp"] <= 0)
    ]

    print("Invalid MSP rows:", len(invalid_msp))


def validate_mandi_references(data, arrivals, prices):
    """Check whether cleaned mandi IDs exist in the master table."""

    print_section("5. REFERENTIAL INTEGRITY")

    master_ids = set(
        data["mandi_master"]["mandi_id"]
        .dropna()
        .apply(normalize_mandi_id)
        .dropna()
    )

    arrival_ids = set(
        arrivals["mandi_id"]
        .dropna()
    )

    price_ids = set(
        prices["mandi_id"]
        .dropna()
    )

    print("Master mandi IDs:", len(master_ids))

    print(
        "Arrival IDs not in master:",
        len(arrival_ids - master_ids)
    )

    print(
        "Price IDs not in master:",
        len(price_ids - master_ids)
    )

    print(
        "Arrival mandi IDs covered by master:",
        len(arrival_ids & master_ids),
        "/",
        len(arrival_ids)
    )

    print(
        "Price mandi IDs covered by master:",
        len(price_ids & master_ids),
        "/",
        len(price_ids)
    )


def validate_transport(transport):
    """Validate transport timing, distance and identifiers."""

    print_section("6. TRANSPORT VALIDATION")

    print("Rows:", len(transport))

    negative_transit = (
        pd.to_numeric(
            transport["transit_hours"],
            errors="coerce"
        ) < 0
    ).sum()

    print("Negative transit hours:", negative_transit)

    print(
        "Missing transit hours:",
        transport["transit_hours"].isna().sum()
    )

    print(
        "Missing departure times:",
        transport["departure_time"].isna().sum()
    )

    print(
        "Missing arrival times:",
        transport["arrival_time"].isna().sum()
    )

    print(
        "Missing distance:",
        transport["distance"].isna().sum()
    )

    print(
        "Missing distance units:",
        transport["distance_unit"].isna().sum()
    )

    print(
        "Missing vehicle numbers:",
        transport["vehicle_no"].isna().sum()
    )

    print(
        "Missing driver IDs:",
        transport["driver_id"].isna().sum()
    )


def validate_weather(weather):
    """Validate weather sensor completeness and units."""

    print_section("7. WEATHER VALIDATION")

    print("Rows:", len(weather))

    print(
        "Missing timestamps:",
        weather["timestamp"].isna().sum()
    )

    print(
        "Missing temperatures:",
        weather["temperature"].isna().sum()
    )

    print(
        "Missing temperature units:",
        weather["temp_unit"].isna().sum()
    )

    print(
        "Missing rainfall:",
        weather["rainfall"].isna().sum()
    )

    print(
        "Missing rainfall units:",
        weather["rain_unit"].isna().sum()
    )

    print(
        "Missing humidity:",
        weather["humidity_percent"].isna().sum()
    )

    print("\nTemperature units:")
    print(
        weather["temp_unit"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.lower()
        .value_counts()
        .to_string()
    )

    print("\nRainfall units:")
    print(
        weather["rain_unit"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.lower()
        .value_counts()
        .to_string()
    )


def validate_crop_normalization(data, arrivals, prices):
    """Verify that all known crop variants map to canonical crops."""

    print_section("8. CROP NORMALIZATION VALIDATION")

    raw_arrival_crops = (
        data["arrivals"]["crop_name"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    raw_price_crops = (
        data["prices"]["crop_name"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    unresolved_arrivals = [
        crop
        for crop in raw_arrival_crops
        if normalize_crop_name(crop) is None
    ]

    unresolved_prices = [
        crop
        for crop in raw_price_crops
        if normalize_crop_name(crop) is None
    ]

    print(
        "Raw arrival crop variants:",
        len(raw_arrival_crops)
    )

    print(
        "Raw price crop variants:",
        len(raw_price_crops)
    )

    print(
        "Unresolved arrival crops:",
        len(unresolved_arrivals)
    )

    print(
        "Unresolved price crops:",
        len(unresolved_prices)
    )

    if unresolved_arrivals:
        print("\nUnresolved arrival crops:")
        print(unresolved_arrivals)

    if unresolved_prices:
        print("\nUnresolved price crops:")
        print(unresolved_prices)

    print("\nCanonical arrival crops:")
    print(
        sorted(
            arrivals["crop_name"]
            .dropna()
            .unique()
            .tolist()
        )
    )

    print("\nCanonical price crops:")
    print(
        sorted(
            prices["crop_name"]
            .dropna()
            .unique()
            .tolist()
        )
    )


def main():
    print_section("DATA VALIDATION REPORT")

    data = load_raw_data()

    # Cleaning is performed here only to validate the curated values.
    arrivals = clean_arrivals(data["arrivals"])
    prices = clean_prices(data["prices"])

    validate_duplicates(data)

    validate_missing_values(data)

    validate_arrivals(arrivals)

    validate_prices(prices)

    validate_mandi_references(
        data,
        arrivals,
        prices
    )

    validate_transport(data["transport"])

    validate_weather(data["weather"])

    validate_crop_normalization(
        data,
        arrivals,
        prices
    )

    print_section("VALIDATION COMPLETE")

    print("Validation checks completed successfully.")


if __name__ == "__main__":
    main()