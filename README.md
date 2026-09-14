DatOps — Mandi-to-Market Supply Chain Optimizer

DatOps is a data-quality-first decision dashboard for the TransOrg AgentIQ Datathon Track 3 (AgriTech).

It turns messy mandi arrivals, prices/MSP, transport, weather, and mandi-master data into a trusted analytical layer, operational risk signals, arrival-shock detection, and a natural-language analytics interface.

What the system does
Raw Data
   ↓
Ingestion
   ↓
Forensics + Cleaning
   ↓
Validation
   ↓
DuckDB analytical layer
   ↓
Analytics
   ↓
Market / Logistics / Weather stress
   ↓
Mandi operational risk
   ↓
Arrival Shock + Action Engine
   ↓
V9 Decision Dashboard + AgriQuery
Core decision questions
Which mandis have the strongest operational pressure?
Where are modal prices falling below MSP?
Which mandis have slower or unusually delayed transport?
How are arrivals moving by crop and over time?
Which recent mandis show a meaningful arrival surge/drop?
What action should an operator investigate first?
Can a natural-language question be translated into an appropriate analytical view?
Data

The supplied bundle contains five source datasets:

Source	Purpose	Key handling
track3_mandi_arrivals.csv	Mandi crop arrivals	Crop/ID/date/unit normalization; quantities converted to KG and Qtl
track3_price_and_msp.json	Wholesale prices and MSP	Currency/numeric parsing; price-order validation
track3_transport_logistics.csv	Mandi-to-warehouse trips	Vehicle normalization; miles→km; invalid transit handling
track3_weather_sensors.xlsx	Sensor weather observations	UTC→IST; F→C; inches→mm; invalid rainfall flagging
track3_mandi_master.csv	Mandi dimension	ID normalization; duplicate master records handled before joins

All supplied data is synthetic and intended for educational/datathon use.

Data rescue

The raw bundle is intentionally messy. The pipeline explicitly surfaces rather than silently hiding source-quality problems.

Examples found during profiling:

Arrivals: 25,750 rows, including 750 exact duplicate rows.
Arrivals contain 36 raw crop-name variants, normalized to six canonical crops.
Arrivals have 5,143 missing unit values.
Transport contains 400 exact duplicate rows and 563 negative transit-hour records.
Weather contains mixed timestamp/timezone formats, Celsius/Fahrenheit temperatures, and mm/inch rainfall.
Weather contains 1,518 negative rainfall values in the raw data; these remain auditable and are excluded from valid rainfall-intensity calculations.
The mandi master contains 60 rows but 57 unique normalized mandi IDs, with 3 duplicate master records.
Prices contain 1,235 missing/unmatched mandi IDs.

The cleaning layer keeps source values where possible and adds explicit status fields such as quantity_status, price_status, transit_status, and rainfall_status.

Analytics
Market pressure

For each mandi/crop, the dashboard uses:

modal price;
MSP;
below-MSP observation rate;
modal-vs-MSP gap.
Logistics pressure

Transport stress uses:

average valid transit hours;
delay rate;
an empirical P90 transit benchmark calculated from valid observations.

The P90 threshold is a dataset-relative benchmark, not a universal service-level agreement.

Weather

Weather is aggregated by IST calendar date.

The supplied workbook does not provide a defensible sensor-to-mandi geography mapping, so DatOps does not fabricate one. Weather is therefore treated as a system-level signal and its relationship with arrivals is presented as descriptive correlation, not causal attribution.

Arrival Shock Radar

Recent arrival intensity is compared with the immediately preceding 30-day window.

The detector:

uses valid standardized arrival quantities;
compares average observed-day arrivals rather than raw period totals;
requires at least 3 observed days in each comparison window;
reports observation coverage;
labels SURGE at ≥ +20% and DROP at ≤ −20%.

This is an anomaly/priority signal, not a forecast or disruption probability.

Action Engine

The action engine combines operational risk and arrival-shock evidence.

Examples:

arrival drop + logistics stress → investigate the supply drop and consider alternate transport/sourcing;
arrival drop + market stress → validate the shortfall and review procurement/market intervention;
arrival surge + logistics stress → prepare for higher inbound volume and monitor congestion;
high operational risk → escalate for operational review.

Recommendations are explainable operational guidance, not guaranteed outcomes.

Explainable risk engine

Risk scores are normalized relative to the observed analytical population.

Market stress: 70% below-MSP rate + 30% negative modal-vs-MSP gap.
Logistics stress: 60% average transit + 40% delay rate.
Weather stress: 70% rainfall intensity + 30% rainy-sensor share.
Mandi operational risk: 50% market + 50% logistics.
System risk: market + logistics + latest weather, with missing components reweighted.

Labels:

HIGH ≥ 80
ELEVATED ≥ 60
WATCH ≥ 40
LOW < 40

A score is a relative prioritization measure. It is not a probability of failure.

AgriQuery

AgriQuery is a safe natural-language analytics router over DuckDB.

It currently supports analytical intents including:

top mandis by arrivals;
arrivals by crop;
mandis below MSP;
transit/delay watchlists;
specific mandi risk;
weather summaries;
daily arrival trends;
crop price vs MSP;
supply-chain stress matrix;
the official-style Wheat + Amritsar + MSP query.

The router selects a chart type such as bar, line, indicator, price comparison, MSP comparison, or stress matrix and generates a text explanation alongside the result.

The official-style query is resolved conservatively: if an exact mandi named in the question is not present, the available master data is used to resolve the location at district level rather than inventing a mandi.

Repository structure
DatOps/
├── app/
│   └── app.py
├── data/
│   └── raw/
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
│   └── validation.py
├── tests/
│   ├── test_analytics_risk.py
│   └── test_pipeline.py
├── .gitignore
├── README.md
└── requirements.txt
Reproduce locally

Python 3.14 was used during development.

Install dependencies:

python -m pip install -r requirements.txt

Build the analytical DuckDB layer:

python src\database.py

Run the data validation report:

python src\validation.py

Run the automated tests:

python -m pytest -q

Run the Agentic Graph AI regression smoke test:

python src\smoke_agent.py

Run the dashboard:

python -m streamlit run app\app.py

The DuckDB file is generated locally at:

data/datops.duckdb

It is intentionally ignored by Git and should not be committed.

Data limitations and assumptions
The dataset is synthetic.
Weather sensors have no reliable sensor-to-mandi mapping in the supplied workbook, so weather is not artificially assigned to individual mandis.
Price and arrival dates have sparse exact (mandi, date, crop) overlap, so the dashboard does not force arbitrary exact-date joins.
The supplied transport data contains warehouse identifiers, but the main risk layer uses mandi-level logistics metrics; unsupported warehouse-level claims are not fabricated.
Negative/invalid source measurements remain visible through status fields where practical and are excluded from metrics that require valid values.
Risk thresholds are dataset-relative prioritization rules, not externally certified operational SLAs.
Evidence of reproducibility

The repository includes:

deterministic ingestion and cleaning functions;
validation checks;
DuckDB database construction;
unit/integration-style tests for cleaning, analytics, risk, and action prioritization;
an Agentic Graph AI smoke-test suite;
data-quality and architecture documentation.
