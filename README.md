# DatOps — Mandi-to-Market Supply Chain Optimizer

**TransOrg AgentIQ Datathon — Track 3: AgriTech**

DatOps is my solution for the Mandi-to-Market Supply Chain problem.

The basic problem is straightforward: an agriculture board needs to know what is happening across mandis — how much crop is arriving, how prices compare with MSP, where transport is getting delayed, and whether weather conditions are associated with changes in arrivals.

The difficult part is getting trustworthy answers from messy source data.

So I built DatOps around this flow:

**messy source data → cleaning → validation → analytical layer → operational signals → dashboard + natural-language analytics**

I intentionally treated data quality as part of the product rather than something to do after building the dashboard.

---

## Quick Overview

| Area | DatOps |
|---|---|
| Track | AgriTech |
| Main problem | Mandi-to-market supply chain monitoring |
| Source datasets | 5 |
| Arrival records | 25,750 |
| Price records | 12,000 |
| Transport records | 10,400 |
| Weather records | 15,000 |
| Canonical crops | 6 |
| Analytical database | DuckDB |
| Dashboard | Streamlit + Plotly |
| Natural-language layer | AgriQuery |
| Risk layer | Market + Logistics + Weather |
| Testing | Pytest + Agent smoke tests |

---

# What DatOps Does

DatOps combines five supplied datasets:

- mandi crop arrivals
- wholesale prices and MSP
- transport/logistics
- weather sensor observations
- mandi master data

The system provides:

- crop arrival analysis
- price vs MSP analysis
- below-MSP monitoring
- mandi-level market pressure
- transport delay analysis
- warehouse performance
- mandi → warehouse route analysis
- weather summaries
- weather/arrival relationship analysis
- recent arrival surge/drop detection
- mandi operational risk scores
- action priorities and recommendations
- interactive dashboard views
- natural-language analytics through **AgriQuery**

The main questions I wanted the system to answer are:

- Which mandis need attention first?
- Which crops are arriving in the largest quantities?
- Where are observed prices below MSP?
- Which mandis are under market pressure?
- Which warehouses have higher transit times or delay rates?
- Which mandi → warehouse routes have frequent delays?
- Which mandis have recently experienced an arrival surge or drop?
- What does the recent weather look like?
- Is rainfall associated with changes in arrivals?
- Why is a particular mandi considered high-risk?
- Can an operator ask a normal question and get the appropriate analytical chart?

---

# Why I Built It This Way

I did not start by building charts.

The first thing I checked was whether the five datasets could actually be used together without producing misleading results.

That turned out to be one of the main challenges.

The source data contains:

- duplicate records
- inconsistent crop names
- mixed units
- inconsistent dates
- missing values
- malformed price strings
- inconsistent mandi IDs
- invalid transport times
- mixed weather units
- mixed weather timezones
- invalid rainfall values

That made the cleaning and validation layer just as important as the dashboard.

I therefore separated the project into three broad stages:

1. **Data rescue and validation**
2. **Analytical layer**
3. **Dashboard and AgriQuery**

The dashboard uses the analytical layer rather than independently cleaning the raw files inside the UI.

This gives the project one place for the business calculations and makes the results easier to reproduce.

---

# Source Data

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

The raw files contain several quality problems.

Rather than hiding them, I profiled the source data first and documented the problems that could affect downstream analysis.

Some of the findings were:

- **25,750** arrival records
- **750** exact duplicate arrival rows
- **36** raw crop-name variants
- **5,143** arrival records with missing units
- **10,400** transport records
- **400** exact duplicate transport rows
- **563** negative transit-hour records
- **1,518** negative rainfall values
- **60** mandi master rows
- **57** unique normalized mandi IDs
- **1,235** price records with missing/unmatched mandi IDs
- **773** price records with missing district values

The six canonical crops are:

```text
wheat
rice
maize
mustard
cotton
sugarcane

Project Architecture
--------------------
                 RAW DATA
                     │
                     ▼
              ┌─────────────┐
              │  ingestion  │
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │  forensics  │
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │   cleaning  │
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │ validation  │
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │   DuckDB    │
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │  analytics  │
              └──────┬──────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       Market     Logistics   Weather
       Stress       Stress      Stress
          │          │          │
          └──────────┼──────────┘
                     ▼
              ┌─────────────┐
              │ Risk Engine │
              └──────┬──────┘
                     ▼
             Arrival Shock Radar
                     │
                     ▼
               Action Engine
                     │
              ┌──────┴──────┐
              ▼             ▼
         Dashboard      AgriQuery