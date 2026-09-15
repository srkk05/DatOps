# DatOps — Mandi-to-Market Supply Chain Optimizer

**TransOrg AgentIQ Datathon — Track 3: AgriTech**

DatOps started with a simple question:

> **Can we give an agriculture operations team one place to see what is happening across mandis, prices, transport and weather — without trusting messy source data blindly?**

The answer became a small data engineering + analytics system rather than just a dashboard.

I built it around one rule:

**clean first → validate second → analyze third**

---

## Live demo

- **Dashboard:** https://datops-mandi2market.streamlit.app/
- **Repository:** https://github.com/srkk05/DatOps

---

## What DatOps does

DatOps combines five supplied datasets:

- mandi arrivals
- wholesale prices + MSP
- transport/logistics
- weather observations
- mandi master data

It turns them into:

- crop arrival analysis
- price vs MSP monitoring
- below-MSP pressure
- transport delay analysis
- warehouse and route analytics
- weather summaries
- rainfall/arrival relationship analysis
- recent arrival surge/drop detection
- mandi operational risk
- action priorities
- natural-language analytics through **AgriQuery**

The main question is:

> **What needs attention, where, and why?**

---

## The pipeline

```text
Raw source data
      ↓
Profile + inspect
      ↓
Clean + standardize
      ↓
Validate
      ↓
DuckDB
      ↓
Business analytics
      ↓
Market / Logistics / Weather signals
      ↓
Risk + Arrival Shock
      ↓
Dashboard + AgriQuery
```

I intentionally kept the analytical calculations outside the dashboard so the UI is not doing its own hidden cleaning or business logic.

---

# 1. Data rescue

This was one of the more important parts of the project.

The raw files contain **63,210 records** across the five datasets.

After the cleaning layer, the analytical database contains **62,057 records**.

| Dataset | Raw | Cleaned | Removed |
|---|---:|---:|---:|
| Arrivals | 25,750 | 25,000 | 750 |
| Prices | 12,000 | 12,000 | 0 |
| Transport | 10,400 | 10,000 | 400 |
| Weather | 15,000 | 15,000 | 0 |
| Mandi master | 60 | 57 | 3 |
| **Total** | **63,210** | **62,057** | **1,153** |

Some of the source problems I found:

- 750 exact duplicate arrival rows
- 400 exact duplicate transport rows
- 3 duplicate mandi-master records after ID normalization
- 36 raw crop-name variants
- missing arrival units
- mixed KG, Qtl and tonne quantities
- mixed miles and kilometres
- messy price strings
- mixed UTC/IST/naive timestamps
- temperatures in °C and °F
- rainfall in mm and inches
- negative transit values
- negative rainfall values
- missing timestamps, vehicle numbers and other fields

I did **not** fill every missing value with a guess.

For operational data, hiding a bad value can be worse than leaving it visible. The cleaning layer therefore creates standardized fields and status/quality information so downstream analytics can decide what is safe to use.

---

# 2. Standardization

The main transformations are:

| Field | Standard form |
|---|---|
| Crop | 6 canonical crop names |
| Mandi ID | `MANDI###` |
| Quantity | KG + Qtl |
| Distance | KM |
| Temperature | °C |
| Rainfall | mm |
| Weather time | UTC + IST |
| Vehicle number | normalized registration format |

For quantities:

```text
1 tonne = 10 Qtl
1 Qtl   = 100 KG
```

The crop mapping handles the English/Hindi/Punjabi variants found in the supplied data.

The implementation lives in:

```text
src/cleaning.py
```

---

# 3. Market analysis

The market layer focuses on observed wholesale prices compared with MSP.

The dashboard can show:

- modal price
- MSP
- below-MSP rate
- modal-vs-MSP gap
- crop-wise price information

I use the **modal price** because it is the price field supplied for the most common observed wholesale value, rather than treating all price fields as interchangeable.

---

# 4. Logistics analysis

For transport I use:

- average transit hours
- median transit hours
- delay rate
- mandi → warehouse routes
- warehouse-level inbound trip activity

The delay benchmark uses the empirical **P90 of valid observed transit times**.

One important limitation:

> The transport source does not contain shipment quantity.

So warehouse "volume" means **inbound trip activity**, not tonnes or Qtl.

I kept that distinction explicit instead of manufacturing a quantity metric.

---

# 5. Weather

The weather workbook contains sensor observations, but it does not provide reliable district/mandi geography.

The datathon notes permit a sensor-location mapping assumption, so DatOps uses a deterministic **sensor → district** mapping for district-level analysis.

The mapping is tracked separately:

```text
data/weather_sensor_district_map.csv
```

This is a **synthetic analytical assumption**, not real-world geography.

I do not assign synthetic weather directly to individual mandis.

The weather layer can therefore support:

- rainfall by district
- recent weather conditions
- district-level rainfall/arrival relationships

The risk engine keeps weather stress at the **system level** rather than pretending the synthetic mapping gives precise mandi-level weather.

---

# 6. Arrival Shock Radar

Average arrival numbers can hide a sudden change.

The Arrival Shock Radar compares:

```text
recent 30-day average observed-day arrivals
                    vs
previous 30-day average observed-day arrivals
```

I require at least 3 observed days in each comparison window.

The classification is:

| Change | Signal |
|---:|---|
| ≥ +20% | SURGE |
| ≤ −20% | DROP |
| otherwise | STABLE |

This is an **attention/anomaly signal**, not a forecast.

I preferred a transparent signal over adding a complicated forecasting model that the supplied data could not really justify.

---

# 7. Risk engine

The risk engine combines market and logistics pressure, with weather used at the system level.

### Market stress

```text
70% below-MSP rate
30% negative modal-vs-MSP gap
```

### Logistics stress

```text
60% average transit
40% delay rate
```

### Weather stress

```text
70% rainfall intensity
30% rainy-sensor share
```

### Mandi operational risk

```text
50% market
50% logistics
```

Risk labels:

| Score | Label |
|---:|---|
| ≥ 80 | HIGH |
| ≥ 60 | ELEVATED |
| ≥ 40 | WATCH |
| < 40 | LOW |

These are **relative prioritization scores**, not probabilities.

For example, a score of 89 does not mean there is an 89% chance of failure. It means the mandi is a high-priority operational signal relative to the supplied data.

---

# 8. Action Engine

I did not want the dashboard to stop at:

> "This mandi is high risk."

The Action Engine combines operational risk with the arrival-shock signal.

Examples:

```text
Arrival DROP + Logistics stress
        ↓
Investigate supply disruption
and transport alternatives
```

```text
Arrival DROP + Market stress
        ↓
Review procurement / market conditions
```

```text
Arrival SURGE + Logistics stress
        ↓
Prepare for possible congestion
and higher inbound activity
```

These are suggested actions to investigate, not guaranteed predictions.

---

# 9. AgriQuery

AgriQuery is the natural-language analytics layer.

It runs through an explicit controlled graph:

```text
QUESTION
   ↓
UNDERSTAND
   ↓
PLAN
   ↓
VALIDATE
   ↓
EXECUTE
   ↓
VISUALIZE
   ↓
EXPLAIN
```

Each node has one responsibility and passes explicit state forward. The planner selects from approved analytical query plans; SQL is validated as read-only before DuckDB execution. This gives the project an inspectable graph workflow without turning it into an unrestricted text-to-SQL generator. The runtime also returns its graph trace so a question's route is auditable.

Example questions:

```text
Show top 5 mandis by arrivals
```

```text
Which mandis are below MSP?
```

```text
What is the risk for MANDI047?
```

```text
Show wheat arrivals for the last 30 days
```

```text
Which mandis have both high price pressure and slow logistics?
```

The flow is:

```text
Question
   ↓
Intent detection
   ↓
Approved query plan
   ↓
DuckDB
   ↓
Data + chart + explanation
```

I chose a **controlled query-plan approach** rather than allowing arbitrary generated SQL to run against the database.

That gives the agent a useful natural-language interface while keeping the database access read-only and predictable.

AgriQuery can select visual outputs such as:

- bar chart
- line chart
- indicator
- price vs MSP comparison
- stress matrix
- table

It also returns a short explanation with the result.

---

## Official-style Wheat / Amritsar query

The datathon includes a query like:

> Plot daily arrival trend of Wheat in Amritsar mandi vs MSP for the last 30 days.

The supplied master does not contain an exact mandi named "Amritsar", and exact `(mandi, date, crop)` price coverage is sparse.

DatOps therefore does not invent missing daily prices just to make the chart look complete.

The query router resolves the available geography conservatively and explains the interpretation in the result.

I would rather return a sparse but truthful result than a polished chart built from fabricated observations.

---

# 10. Why DuckDB?

DuckDB fits the project because the analytical layer mainly needs:

- SQL aggregations
- joins
- filtering
- local analytics
- a reproducible generated database

The database is rebuilt from the supplied raw files.

It is not treated as another source of truth.

---

# 11. Project structure

```text
DatOps/
├── app/
│   └── app.py
├── data/
│   ├── raw/
│   └── weather_sensor_district_map.csv
├── docs/
│   ├── advanced_insights.md
│   ├── architecture.md
│   ├── data_dictionary.md
│   └── data_quality.md
├── src/
│   ├── agent.py
│   ├── analytics.py
│   ├── cleaning.py
│   ├── database.py
│   ├── forensics.py
│   ├── ingestion.py
│   ├── profile.py
│   ├── risk_engine.py
│   ├── smoke_agent.py
│   ├── validation.py
│   └── weather_mapping.py
├── tests/
│   ├── test_analytics_risk.py
│   └── test_pipeline.py
├── .gitignore
├── README.md
└── requirements.txt
```

---

# 12. Running locally

I used Python 3.14 for the project.

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

### Build the analytical database

```powershell
python src\database.py
```

Expected row counts:

```text
mandi_master       57
arrivals        25000
prices          12000
transport       10000
weather         15000
```

### Run validation

```powershell
python src\validation.py
```

The validation report checks:

- raw → cleaned row counts
- missing values
- quantity validity
- price validity
- referential integrity
- mandi-master uniqueness
- transport quality
- weather quality
- crop normalization

### Run tests

```powershell
python -m pytest -q
```

Current verified result:

```text
18 passed
```

### Run the AgriQuery smoke tests

```powershell
python src\smoke_agent.py
```

### Run the dashboard

```powershell
python -m streamlit run app\app.py
```

---

# 13. Documentation

More detailed project notes are in:

- `docs/data_dictionary.md` — fields, units and joins
- `docs/data_quality.md` — profiling and cleaning evidence
- `docs/architecture.md` — system design
- `docs/advanced_insights.md` — anomaly and risk methodology

---

# 14. Limitations

### Sparse price/arrival overlap

Exact `(mandi, date, crop)` overlap between arrival and price facts is sparse.

I avoid forcing arbitrary exact-date joins or inventing missing observations.

### Weather geography

The source does not provide reliable sensor → mandi geography.

District-level weather analysis uses the tracked synthetic sensor → district mapping. Mandi-level weather attribution is not claimed.

### Synthetic source data

The supplied dataset is synthetic, so the results should not be interpreted as a real agricultural market forecast.

### Risk interpretation

Risk is an operational prioritization mechanism, not a probability model.

### Machine learning

I explored forecasting and clustering approaches, but the available data did not justify adding a complicated model just for the sake of calling it AI.

The final product favors transparent, testable signals where they are more defensible.

---

# 15. Final verification

Before submission I run:

```powershell
python src\database.py
python src\validation.py
python -m pytest -q
python src\smoke_agent.py
python -m streamlit run app\app.py
```

The important part is that the same raw data can reproduce the analytical layer and the dashboard numbers can be traced back through the pipeline.

**DatOps is essentially a mandi operations cockpit built on top of a data-quality pipeline.**
