# Advanced Insights & Data Trust

## Arrival Shock Detector

To identify sudden changes in mandi arrivals, DatOps compares the most recent 30-day period with the previous 30-day period.

The analysis:

* considers only arrivals marked as `quantity_status = VALID`;
* aggregates the quantity received at each mandi for each observed day;
* compares the **average arrival on observed days** instead of comparing raw 30-day totals;
* requires at least 3 observed days in each period before reporting a result;
* shows the number of observed days so that low data coverage is not hidden;
* classifies the change as `SURGE` when it is at least +20%, `DROP` when it is at most -20%, and `STABLE` otherwise.

This is intended as a descriptive signal for unusual changes in arrivals, not as a forecast or a probability of future disruption.

### Why observed-day normalization is used

A mandi may have fewer records in one period because of missing or incomplete reporting. Comparing raw totals in that situation could make a normal reporting gap look like a supply collapse.

Using the average arrival for days that were actually observed gives a fairer comparison and also allows the dashboard to show the data coverage alongside the result.

## Action Engine

The Action Engine combines the main signals already calculated in the analytics layer:

* operational risk score;
* arrival shock and its direction;
* market stress;
* logistics stress.

These signals are used to assign an operational priority and suggest a possible next action.

For example:

* **Arrival drop + logistics stress:** investigate the supply reduction and consider alternate transport or sourcing options.
* **Arrival drop + market stress:** verify the shortfall and review whether procurement or market intervention is required.
* **Arrival surge + logistics stress:** prepare for possible congestion due to higher inbound volumes.
* **High operational risk:** flag the mandi for further operational review.

The recommendations are meant to support decision-making. They are not presented as guaranteed predictions or outcomes.

## Data Trust

Data-quality checks are carried through the pipeline instead of being treated as a one-time cleaning step.

Key decisions include:

* crop names are mapped to six standard crop categories;
* quantities recorded in KG, Qtl and tonnes are converted into consistent units;
* duplicate records are identified before aggregation;
* duplicate mandi master records are resolved before joining with transaction data;
* invalid or negative transit values are excluded from logistics calculations;
* negative rainfall values are retained for auditability but excluded from rainfall-intensity calculations;
*weather is used for district-level analysis through the tracked synthetic sensor→district mapping permitted by the competition notes. DatOps does not claim mandi-level weather attribution; the risk engine continues to use weather as a system-level signal.
* price and arrival records are not forced into exact-date joins when there is insufficient temporal overlap to support a meaningful comparison.

These checks help prevent data-quality issues from silently affecting the final metrics and dashboard.

## Reproducibility

The complete analytical pipeline can be reproduced using:

```powershell
python src\database.py
python -m pytest -q
python src\analytics.py
```

The resulting DuckDB analytical layer is then used by the dashboard.

This keeps the dashboard separate from the raw data and ensures that the same cleaning, validation and analytical logic is applied whenever the pipeline is run again.
