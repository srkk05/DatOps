# Data Quality & Data Trust

## Raw profiling snapshot

| Dataset      |   Rows | Exact duplicate rows |
| ------------ | -----: | -------------------: |
| Arrivals     | 25,750 |                  750 |
| Prices       | 12,000 |                    0 |
| Transport    | 10,400 |                  400 |
| Weather      | 15,000 |                    0 |
| Mandi master |     60 |                    3 |

The raw files were profiled before cleaning. Duplicate detection, missing-value analysis, type checks, unit inconsistencies, and logical validation were performed before analytical tables were built.

## Important missing values

### Arrivals

* `unit`: **5,143**
* `farmer_count`: **3,899**
* `variety`: **3,735**
* `arrival_id`: **484**

Missing units are treated as a real data-quality issue. Without a reliable unit, the source quantity cannot be safely converted and is therefore excluded from standardized arrival metrics.

### Prices

* `mandi_id`: **1,235**
* `district`: **773**

Price records with a missing `mandi_id` remain in the fact table for traceability, but are not assigned to a mandi during dimensional analysis.

### Transport

* `vehicle_no`: **1,622**
* `driver_id`: **1,551**
* `arrival_time`: **1,053**
* `distance_unit`: **1,032**
* `transit_hours`: **518**

The source contains **563 negative transit-hour values**. These records are retained for auditability and marked through `transit_status`, but are excluded from valid logistics metrics.

### Weather

* `timestamp`: **1,555**
* `temp_unit`: **2,263**
* `humidity_percent`: **1,500**
* `rainfall`: **791**
* `rain_unit`: **791**

Some missing temperature units can be recovered when the raw temperature value itself contains an explicit `°C` or `°F` marker. Remaining ambiguous values are not assigned a unit by assumption.

## Standardization

The arrivals and price datasets contain **36 raw crop-name variants**. These are mapped to six canonical crops:

```text
cotton
maize
mustard
rice
sugarcane
wheat
```

Mandi identifiers are normalized to:

```text
MANDI###
```

Other standardizations include:

```text
KG / Qtl / Tonne  →  standardized quantity fields
Miles             →  KM
°F                →  °C
Inches            →  mm
Mixed timestamps  →  UTC + IST
```

The same canonical crop and mandi mappings are used across datasets to keep cross-table analysis consistent.

## Negative source values

Negative values are **not silently overwritten**.

For rainfall, the converted value is retained and its validity is recorded through `rainfall_status`. Invalid negative rainfall is excluded from valid rainfall-intensity calculations.

The same approach is used for negative transit hours through `transit_status`.

This creates a deliberate distinction between:

```text
value exists in the source
          vs.
value is valid for analysis
```

The raw issue remains traceable without allowing it to distort business metrics.

## Referential integrity

After mandi-ID normalization:

* arrivals use the normalized `mandi_id` for master coverage checks;
* price records with non-null normalized `mandi_id` can be validated against the master;
* transport records use the same canonical mandi key;
* duplicate mandi master IDs are resolved before analytical joins.

The source mandi master contains **60 rows but only 57 unique mandi IDs**. Joining the raw master directly could therefore multiply fact rows. DatOps uses a deduplicated master view before joining arrivals, prices, or transport.

## Temporal integrity

Price and arrival data have sparse exact `(mandi, date, crop)` overlap.

DatOps therefore does not manufacture missing daily observations or force an exact-date fact join where the source does not provide sufficient overlap.

For trend analysis, the system uses the actual arrival observations and available MSP information as a reference where supported.

## Weather geography limitation

The supplied weather workbook contains sensor observations but no reliable sensor-to-mandi location field.

DatOps therefore does **not** claim:

```text
sensor X → mandi Y
```

unless that relationship is supported by the source.

Weather is consequently retained as a **system/date-level signal**, avoiding unsupported mandi-level weather conclusions.

## Risk interpretation

Risk is designed for **relative prioritization**, not prediction.

* Scores are relative to the observed dataset.
* Percentile normalization prevents raw metric scale from dominating the score.
* Missing components are reweighted rather than silently treated as zero.
* `HIGH`, `ELEVATED`, `WATCH`, and `LOW` represent operational priority levels.

The risk score is **not** a probability of disruption, failure, or price crash.

## Validation commands

```powershell
python src\validation.py
python -m pytest -q
```

The automated test suite covers:

* risk-score bounds;
* single-observation neutral scoring;
* missing-component weight re-normalization;
* stress labels;
* arrival-shock direction and coverage;
* action-engine priority logic;
* cleaning and normalization invariants.
