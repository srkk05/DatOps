DatOps — Mandi-to-Market Supply Chain Optimizer

TransOrg AgentIQ Datathon — Track 3: AgriTech

DatOps started with a fairly simple question:

Can we give an agriculture operations team one place to see what is happening across mandis, prices, transport and weather — without trusting messy source data blindly?

The answer became a small data engineering + analytics system rather than just a dashboard.

I built the pipeline around one rule: clean first, validate second, analyze third.

The idea

A mandi can have a good arrival day but a bad market price.
A warehouse can have enough inbound activity but unusually high transit times.
A sudden arrival drop can be worth investigating even when the average numbers still look normal.

So instead of showing one giant table, DatOps combines a few operational signals:

Raw data
   ↓
Profile + inspect
   ↓
Clean + standardize
   ↓
Validate
   ↓
DuckDB
   ↓
Analytics
   ↓
Risk + Arrival Shock
   ↓
Dashboard + AgriQuery

The goal is not to predict everything.

The goal is to help an operator answer:

"What needs my attention right now, and why?"

Live demo

Dashboard: https://datops-mandi2market.streamlit.app/

GitHub: https://github.com/srkk05/DatOps

What is in the data?

The datathon bundle has five sources:

Dataset

What I use it for

Mandi arrivals

Crop arrivals and supply trends

Prices + MSP

Wholesale price pressure

Transport logistics

Transit and delay analysis

Weather sensors

Weather conditions and rainfall

Mandi master

Mandi/district reference data

The supplied data is synthetic.

1. The part I spent the most time on: data rescue

The raw data looked usable at first glance, but there were quite a few things that could quietly break the analysis.

Across the five datasets there are 63,210 raw records.

After cleaning, the analytical layer has 62,057 records.

Dataset

Raw

Cleaned

Removed

Arrivals

25,750

25,000

750

Prices

12,000

12,000

0

Transport

10,400

10,000

400

Weather

15,000

15,000

0

Mandi master

60

57

3

Total

63,210

62,057

1,153

Some of the problems I found:

750 exact duplicate arrival rows

400 exact duplicate transport rows

3 duplicate mandi-master records after ID normalization

36 different crop-name variants which reduce to 6 canonical crops

mixed KG, Qtl and tonne units

mixed miles and kilometres

prices containing messy currency/string formats

UTC, IST and naive timestamps

temperatures in both °C and °F

rainfall in both mm and inches

negative transit values

negative rainfall values

missing timestamps, units, vehicle numbers and other fields

I deliberately did not fill every missing value with a guessed value.

For operational data, hiding a bad value can be worse than leaving it visible.

Instead, the cleaning layer adds standardized fields and status/quality information so downstream analytics can decide what is safe to use.

2. Standardization

The main transformations are:

Field

Standard form

Crop

6 canonical crop names

Mandi ID

MANDI###

Quantity

KG + Qtl

Distance

KM

Temperature

°C

Rainfall

mm

Weather time

UTC + IST

Vehicle number

normalized registration format

For example:

1 tonne = 10 Qtl
1 Qtl   = 100 KG

Crop variants such as English/Hindi/Punjabi spellings are mapped into a common crop vocabulary.

The exact mappings live in src/cleaning.py.

3. Market analysis

The market side focuses on the relationship between observed wholesale prices and MSP.

The dashboard can show:

modal price

MSP

below-MSP observations

modal-vs-MSP gap

crop-wise price information

I use the modal price rather than simply averaging all price fields because the modal value is the field that represents the most common observed wholesale price in the supplied data.

4. Logistics analysis

For transport I look at:

average transit hours

median transit hours

delay rate

mandi → warehouse routes

warehouse-level inbound trip activity

The delay benchmark is based on the empirical P90 of valid observed transit times.

One important limitation:

The transport source does not contain shipment quantity.

So when I talk about warehouse "volume", I mean inbound trip activity, not tonnes or Qtl.

I kept this distinction explicit rather than manufacturing a volume metric.

5. Weather

This part needed an assumption.

The weather workbook has sensor IDs and observations, but it does not provide reliable district or mandi geography.

The datathon notes allow a sensor-location mapping assumption, so I created a deterministic sensor → district mapping for district-level analysis.

That mapping is stored separately:

data/weather_sensor_district_map.csv

I am treating this as a synthetic analytical assumption, not real geography.

I also do not assign weather directly to individual mandis.

The weather layer can therefore answer things like:

rainfall by district

recent weather conditions

rainfall/arrival relationship by district

The risk engine keeps weather stress at the system level, because attaching synthetic weather to a particular mandi would give a false sense of precision.

6. Arrival Shock Radar

Average arrival numbers can hide a sudden change.

So I added a simple arrival-shock detector.

It compares:

recent 30-day average observed-day arrivals

against

the previous 30-day average observed-day arrivals.

I require at least 3 observed days in each comparison window.

The result is:

SURGE   >= +20%
DROP    <= -20%
STABLE  otherwise

This is intentionally simple.

It is an anomaly/attention signal, not a forecast.

That makes it easier to explain to someone looking at the dashboard and also avoids pretending that the synthetic dataset supports a sophisticated forecasting model when it does not.

7. Risk engine

The risk engine combines three areas of pressure:

Market

70% below-MSP rate

30% negative modal-vs-MSP gap

Logistics

60% average transit

40% delay rate

Weather

70% rainfall intensity

30% rainy-sensor share

Mandi operational risk is:

50% market
50% logistics

System risk also considers the latest valid weather signal.

The final labels are:

Score

Label

80+

HIGH

60–79.99

ELEVATED

40–59.99

WATCH

<40

LOW

These are relative prioritization scores, not probabilities.

In other words, a HIGH mandi does not mean "80% chance of failure".

It means that, relative to the observed data, this mandi deserves more attention.

8. Action Engine

I didn't want the dashboard to stop at:

"This mandi is high risk."

So the Action Engine combines operational risk with the arrival-shock signal.

For example:

Arrival DROP + Logistics stress
        ↓
Investigate supply disruption
and transport alternatives

Arrival DROP + Market stress
        ↓
Review procurement / market conditions

Arrival SURGE + Logistics stress
        ↓
Prepare for possible congestion
and higher inbound activity

The recommendations are deliberately phrased as actions to investigate, not guaranteed predictions.

9. AgriQuery

AgriQuery is the natural-language part of DatOps.

You can ask questions like:

Show top mandis by arrivals

Show wheat daily arrivals

Which mandis have the highest transit delay?

Show rice price vs MSP

Show the mandi risk for MANDI047

The flow is:

Question
   ↓
Intent detection
   ↓
Approved query plan
   ↓
DuckDB
   ↓
Data + chart + explanation

I chose a controlled query-plan approach instead of allowing arbitrary generated SQL.

That means the agent can understand a useful set of natural-language questions while keeping database access read-only and predictable.

Depending on the question, AgriQuery selects an appropriate visualization such as:

bar chart

line chart

indicator

price vs MSP comparison

stress matrix

table

It also returns a short explanation alongside the result.

10. A note about the official Wheat / Amritsar query

The datathon includes a query along the lines of:

Plot daily arrival trend of Wheat in Amritsar mandi vs MSP for the last 30 days.

The source data does not give us enough exact (mandi, date, crop) price coverage to honestly manufacture a complete daily price series.

So DatOps does not create missing daily prices just to make the chart look complete.

The query router resolves available geography conservatively and uses only observations supported by the data.

This was an important design choice for me: a less impressive-looking truthful result is better than a polished fabricated one.

11. Why DuckDB?

I used DuckDB as the local analytical layer because the project mostly needs:

SQL aggregations

joins

filtering

fast local analytics

a reproducible generated database

The database is rebuilt from the raw files.

It is not treated as another source of truth.

Project structure

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

Running it locally

I used Python 3.14 for the project.

Install dependencies:

python -m pip install -r requirements.txt

Build the database

python src\database.py

Expected analytical row counts:

mandi_master       57
arrivals        25000
prices          12000
transport       10000
weather         15000

Run validation

python src\validation.py

This prints the data-quality checks, including:

raw vs cleaned row counts

missing values

crop normalization

quantity checks

price checks

referential integrity

transport validation

weather validation

Run tests

python -m pytest -q

Current result:

18 passed

Run the agent smoke test

python src\smoke_agent.py

Run the dashboard

python -m streamlit run app\app.py

Documentation

If you want the details rather than just the dashboard:

docs/data_dictionary.md — fields, units and joins

docs/data_quality.md — profiling and cleaning evidence

docs/architecture.md — system design

docs/advanced_insights.md — anomaly/risk methodology

Things I would not claim from this dataset

There are a few limitations worth being explicit about.

Sparse price/arrival overlap

Exact (mandi, date, crop) overlap between arrival and price facts is sparse.

I therefore avoid forcing arbitrary exact-date joins or inventing missing observations.

Weather geography

The source does not provide reliable sensor→mandi geography.

District-level weather analysis uses the tracked synthetic mapping described above.

Mandi-level weather attribution is not claimed.

Synthetic data

The dataset is synthetic, so the results should not be interpreted as a real agricultural market forecast.

Risk scores

Risk is a prioritization mechanism, not a probability model.

Machine learning

I explored forecasting and clustering approaches, but the available data did not justify adding a complicated model just for the sake of calling it AI.

The final product favors transparent, testable signals where they are more defensible.

Final check

Before submitting, I run:

python src\database.py
python src\validation.py
python -m pytest -q
python src\smoke_agent.py
python -m streamlit run app\app.py

The important part for me is that the same raw data can reproduce the analytical layer and that the dashboard numbers can be traced back through the pipeline.

DatOps is basically a mandi operations cockpit built on top of a data-quality pipeline. It is a tool that helps you to understand the data you have and how it can be used to build a model.