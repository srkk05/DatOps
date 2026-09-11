from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
#creating a loader function to read files everywhere
def load_raw_data():
    arrivals = pd.read_csv(RAW_DIR / "track3_mandi_arrivals.csv")
    prices = pd.read_json(RAW_DIR / "track3_price_and_msp.json")
    weather = pd.read_excel(RAW_DIR / "track3_weather_sensors.xlsx")
    transport = pd.read_csv(RAW_DIR / "track3_transport_logistics.csv")
    mandi_master = pd.read_csv(RAW_DIR / "track3_mandi_master.csv")

    return {
        "arrivals": arrivals,
        "prices": prices,
        "weather": weather,
        "transport": transport,
        "mandi_master": mandi_master,
    }

if __name__ == "__main__":
    data = load_raw_data()

    for name, df in data.items():
        print("=" * 60)
        print(name.upper())
        print("=" * 60)
        print("Rows:", len(df))
        print("Columns:", len(df.columns))
        print("Column names:")
        print(df.columns.tolist())
        print()