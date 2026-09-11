from ingestion import load_raw_data

def profile_dataset(name, df):
    print("\n" + "=" * 80)
    print(f"DATASET: {name.upper()}")
    print("=" * 80)
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")
    print("\nColumn types:")
    print(df.dtypes)

    print("\nMissing values:")
    missing = df.isna().sum()
    missing = missing[missing > 0].sort_values(ascending=False)

    if len(missing):
        print(missing)
    else:
        print("No missing values")

    print("\nDuplicate rows:")
    print(df.duplicated().sum())
    print("\nSample:")
    print(df.head(3).to_string(index=False))


if __name__ == "__main__":
    data = load_raw_data()
    for name, df in data.items():
        profile_dataset(name, df)