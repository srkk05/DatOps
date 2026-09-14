# DatOps — Mandi-to-Market Supply Chain Optimizer

My submission for the **TransOrg AgentIQ Datathon — Track 3: AgriTech**.

The problem I focused on is fairly simple:

A State Agriculture Board needs to understand what is happening across mandis — how much crop is arriving, whether prices are above or below MSP, where transport is getting delayed, and whether weather conditions are related to changes in arrivals.

The difficult part is that the source data is messy.

So I built DatOps around this flow:

**messy data → cleaned data → validated analytics → operational signals → dashboard + natural-language queries**

I deliberately focused on making the data pipeline reliable before building the dashboard.

---

## What DatOps does

DatOps combines five supplied datasets:

- mandi crop arrivals
- wholesale prices and MSP
- transport/logistics
- weather sensor observations
- mandi master data

The system provides:

- crop arrival analysis
- price vs MSP analysis
- mandi-level market pressure
- transport delay analysis
- warehouse and route performance
- weather summaries
- recent arrival surge/drop detection
- mandi operational risk scores
- recommended actions for investigation
- an interactive Streamlit dashboard
- **AgriQuery**, a natural-language analytics interface

The main questions I wanted the dashboard to answer are:

- Which mandis need attention first?
- Where are prices below MSP?
- Which transport routes have unusually high delays?
- Which crops are seeing arrival increases or decreases?
- Which mandis have recently experienced a significant arrival change?
- Is weather associated with changes in arrivals?
- What should an operator investigate first?
- Can a normal question be converted into the right analytical chart?

---

# Why I built it this way

I did not start by building charts.

The first thing I checked was whether the five datasets could actually be used together without creating misleading numbers.

There were duplicate records, mixed crop names, different units, inconsistent dates, missing values, malformed price fields, invalid transport times and invalid rainfall values.

That made the data-cleaning part just as important as the dashboard.

I therefore separated the project into three main stages:

1. **Data rescue and validation**
2. **Analytical layer**
3. **Dashboard and AgriQuery**

The dashboard reads from the analytical layer instead of independently cleaning and calculating everything inside the UI.

This keeps the calculations consistent and makes the pipeline easier to reproduce.

---

# Data

The supplied bundle contains five source datasets.

| Source | Purpose | Main cleaning |
|---|---|---|
| `track3_mandi_arrivals.csv` | Daily crop arrivals | Crop/date/mandi normalization, unit conversion, quantity validation |
| `track3_price_and_msp.json` | Wholesale prices and MSP | Numeric/currency parsing, crop normalization, price validation |
| `track3_transport_logistics.csv` | Mandi-to-warehouse trips | Vehicle normalization, miles → km, transit validation |
| `track3_weather_sensors.xlsx` | Weather observations | UTC → IST, °F → °C, inches → mm, rainfall validation |
| `track3_mandi_master.csv` | Mandi reference data | Mandi ID normalization and duplicate handling |

The supplied data is synthetic and intended for the datathon.

---

# Data Rescue

The raw files are intentionally inconsistent. I wanted to keep those problems visible instead of simply dropping everything that looked unusual.

Some of the issues found during profiling:

- **25,750** arrival records
- **750** exact duplicate arrival rows
- **36** raw crop-name variants reduced to **6 canonical crops**
- **5,143** arrival records with missing units
- **10,400** transport records
- **400** exact duplicate transport rows
- **563** negative transit-hour records
- **1,518** negative rainfall values
- **60** mandi master rows but only **57** unique normalized mandi IDs
- **1,235** price records with missing/unmatched mandi IDs

The six canonical crops are:

- Wheat
- Rice
- Maize
- Mustard
- Cotton
- Sugarcane

## I did not silently delete every bad value

Where possible, the pipeline keeps the source value and adds a status field describing whether it is usable for a particular analysis.

Examples:

```text
quantity_status
price_status
transit_status
rainfall_status