# Architecture
## System Flow

* raw files
       │
       ▼
src/ingestion.py
       │
       ├── src/forensics.py
       │       └── source-quality investigation
       │
       ▼
src/cleaning.py
       │
       ├── crop and mandi standardization
       ├── date and numeric parsing
       ├── quantity and unit conversion
       ├── price normalization
       ├── transport normalization
       └── weather timezone and unit normalization
       │
       ▼
src/validation.py
       │
       ├── duplicate checks
       ├── missing-value checks
       ├── logical value checks
       ├── referential integrity
       └── normalization checks
       │
       ▼
src/database.py
       │
       ▼
DuckDB analytical layer
       ├── mandi_master
       ├── arrivals
       ├── prices
       ├── transport
       └── weather
       │
       ├──────────────────────┐
       ▼                      ▼
src/analytics.py       src/risk_engine.py
       │                      │
       │              market / logistics /
       │                weather stress
       │                      │
       │                operational risk
       │                      │
       └── arrival shock ─────┤
                              ▼
                       action_engine()
                              │
                              ▼
                        app/app.py
                              │
                              ▼
                        dashboard
                              │
                              ▼
                        src/agent.py
                              │
                              ▼
                           AgriQuery
```

## Design Principles

### 1. Data Quality Before Analytics

The dashboard does not directly use raw source files for decision-making metrics. Data first passes through ingestion, cleaning, and validation before being materialized into the DuckDB analytical layer.

This keeps dashboard metrics consistent and makes the data pipeline reproducible.

### 2. Preserve Auditability

Problematic records are not silently removed wherever possible. The pipeline adds standardized fields and status columns so that data-quality decisions remain traceable.

Examples include:

* `arrival_quantity_kg`
* `arrival_quantity_qtl`
* `quantity_status`
* `price_status`
* `vehicle_no_normalized`
* `distance_km`
* `transit_status`
* `timestamp_utc`
* `timestamp_ist`
* `weather_date_ist`
* `temperature_c`
* `rainfall_mm`
* `rainfall_status`

This allows the analytical layer to use only valid records while still keeping the original quality issues visible for audit and debugging.

### 3. Protect Joins From Dirty Dimensions

The mandi master contains duplicate IDs, so the master dimension is deduplicated before it is joined with transaction data.

This prevents one-to-many joins from artificially multiplying arrival, price, or transport records and producing incorrect dashboard metrics.

### 4. Avoid Unsupported Inference

The supplied weather data does not provide reliable source geography. DatOps therefore uses the tracked synthetic sensor→district mapping permitted by the competition notes for district-level weather analysis. Multiple sensors may map to a district, while UNKNOWN sensors remain unattributed. This is an analytical assumption, not claimed real-world geography. Weather is not assigned to individual mandis, and the risk engine continues to treat weather as a system-level signal.

The same principle is applied to price and arrival data. When temporal overlap is too sparse, the pipeline does not create artificial exact-date relationships just to produce a correlation.

### 5. Keep Risk Explainable

Risk scores are calculated using deterministic weighted combinations of observed metrics with percentile-based relative normalization.

The underlying metrics remain visible alongside the final score, so a high-risk result can be traced back to the factors contributing to it.

### 6. Keep Natural-Language Analytics Controlled

AgriQuery converts supported natural-language questions into predefined analytical plans. The selected SQL is validated before execution, followed by chart selection and a short explanation of the result.

The implementation is intentionally constrained to supported analytical patterns rather than presenting itself as a general-purpose LLM system. This improves reliability and makes the generated insights easier to verify.

## Runtime Components

| Component        | Responsibility                                                                  |
| ---------------- | ------------------------------------------------------------------------------- |
| `ingestion.py`   | Load the supplied raw files                                                     |
| `forensics.py`   | Investigate messy values and source-quality issues                              |
| `cleaning.py`    | Standardize fields, dates, values, and units                                    |
| `validation.py`  | Check data constraints and cleaned/raw relationships                            |
| `database.py`    | Build the reproducible DuckDB analytical layer                                  |
| `analytics.py`   | Generate arrival-shock and transit analytics                                    |
| `risk_engine.py` | Calculate explainable market, logistics, and weather risk                       |
| `agent.py`       | Handle natural-language planning, SQL execution, chart selection, and summaries |
| `app.py`         | Serve the Streamlit decision dashboard                                       |
| `tests/`         | Provide automated regression coverage                                           |

## Deployment

The DuckDB database is treated as a build artifact rather than a source file. During deployment, the analytical layer should be rebuilt or provided before the dashboard starts serving queries.

Generated `.duckdb` files are therefore excluded from the repository, while the scripts required to reproduce the database are committed to GitHub.
