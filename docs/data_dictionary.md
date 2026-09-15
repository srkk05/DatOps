# Data Dictionary

## 1. Arrivals

**Source:** `track3_arrivals.*`

| Field                  | Description               | Data Type   | Cleaning / Validation                                  |
| ---------------------- | ------------------------- | ----------- | ------------------------------------------------------ |
| `arrival_id`           | Arrival record identifier | String      | Preserved; missing values flagged                      |
| `date`                 | Arrival date              | Date        | Parsed and standardized                                |
| `mandi_id`             | Mandi identifier          | String      | Normalized to `MANDI###`                               |
| `crop_name`            | Crop name                 | String      | Mapped to 6 canonical crops                            |
| `variety`              | Crop variety              | String      | Preserved                                              |
| `arrival_quantity`     | Reported arrival quantity | Numeric     | Parsed from source                                     |
| `unit`                 | Quantity unit             | String      | Normalized to KG / Qtl / Tonne                         |
| `farmer_count`         | Number of farmers         | Numeric     | Preserved                                              |
| `arrival_quantity_kg`  | Standardized quantity     | Numeric     | Derived from quantity + unit                           |
| `arrival_quantity_qtl` | Quantity in quintals      | Numeric     | `kg / 100`                                             |
| `quantity_status`      | Quantity quality flag     | Categorical | `VALID`, `MISSING`, `INVALID_NEGATIVE`, `INVALID_UNIT` |

**Canonical crops:** `cotton`, `maize`, `mustard`, `rice`, `sugarcane`, `wheat`

---

## 2. Price & MSP

**Source:** `track3_price_and_msp.json`

| Field          | Description             | Data Type   | Cleaning / Validation             |
| -------------- | ----------------------- | ----------- | --------------------------------- |
| `record_id`    | Price record identifier | String      | Preserved                         |
| `date`         | Price observation date  | Date        | Parsed and standardized           |
| `mandi_id`     | Mandi identifier        | String      | Normalized to `MANDI###`          |
| `crop_name`    | Crop name               | String      | Same canonical crop mapping       |
| `district`     | District                | String      | Trimmed; missing values retained  |
| `min_price`    | Minimum wholesale price | Numeric     | Currency/numeric parsing          |
| `modal_price`  | Modal wholesale price   | Numeric     | Currency/numeric parsing          |
| `max_price`    | Maximum wholesale price | Numeric     | Currency/numeric parsing          |
| `msp`          | Minimum Support Price   | Numeric     | Currency/numeric parsing          |
| `price_status` | Price quality flag      | Categorical | Validated using min ≤ modal ≤ max |

---

## 3. Transport & Logistics

**Source:** `track3_transport_logistics.csv`

| Field                   | Description             | Data Type   | Cleaning / Validation                  |
| ----------------------- | ----------------------- | ----------- | -------------------------------------- |
| `trip_id`               | Trip identifier         | String      | Preserved                              |
| `mandi_id`              | Origin mandi            | String      | Normalized                             |
| `vehicle_no`            | Source vehicle number   | String      | Preserved                              |
| `driver_id`             | Driver identifier       | String      | Preserved                              |
| `departure_time`        | Departure timestamp     | Datetime    | Parsed                                 |
| `arrival_time`          | Arrival timestamp       | Datetime    | Parsed                                 |
| `distance`              | Reported distance       | Numeric     | Parsed                                 |
| `distance_unit`         | Distance unit           | String      | Normalized                             |
| `destination_warehouse` | Destination warehouse   | String      | Preserved                              |
| `transit_hours`         | Transit duration        | Numeric     | Extracted from formatted values        |
| `vehicle_no_normalized` | Standard vehicle number | String      | Formatting normalized                  |
| `distance_km`           | Distance in kilometres  | Numeric     | Miles converted to KM                  |
| `transit_status`        | Transit quality flag    | Categorical | `VALID`, `MISSING`, `INVALID_NEGATIVE` |

---

## 4. Weather

**Source:** `track3_weather_sensors.xlsx`

| Field              | Description               | Data Type   | Cleaning / Validation                                      |
| ------------------ | ------------------------- | ----------- | ---------------------------------------------------------- |
| `sensor_id`        | Weather sensor identifier | String      | Preserved                                                  |
| `timestamp`        | Source observation time   | Datetime    | Mixed timezone parsing                                     |
| `temperature`      | Recorded temperature      | Numeric     | Numeric extraction                                         |
| `temp_unit`        | Temperature unit          | String      | Normalized; embedded °C/°F handled                         |
| `rainfall`         | Recorded rainfall         | Numeric     | Numeric extraction                                         |
| `rain_unit`        | Rainfall unit             | String      | Normalized                                                 |
| `humidity_percent` | Relative humidity         | Numeric     | Preserved                                                  |
| `timestamp_utc`    | Standard UTC timestamp    | Datetime    | Converted to UTC                                           |
| `timestamp_ist`    | India-local timestamp     | Datetime    | Converted to IST                                           |
| `weather_date_ist` | IST calendar date         | Date        | Derived from IST timestamp                                 |
| `temperature_c`    | Temperature in Celsius    | Numeric     | °F converted to °C                                         |
| `rainfall_mm`      | Rainfall in millimetres   | Numeric     | Inches converted to mm                                     |
| `rainfall_status`  | Rainfall quality flag     | Categorical | Negative values flagged and excluded from rainfall metrics |

---

## 5. Mandi Master

**Source:** `track3_mandi_master.csv`

| Field              | Description      | Data Type | Cleaning / Validation    |
| ------------------ | ---------------- | --------- | ------------------------ |
| `mandi_id`         | Mandi identifier | String    | Normalized to `MANDI###` |
| `mandi_name`       | Mandi name       | String    | Trimmed                  |
| `district`         | District         | String    | Trimmed                  |
| `state`            | State            | String    | Trimmed                  |
| `mandi_type`       | Mandi category   | String    | Trimmed                  |
| `total_area_acres` | Mandi area       | Numeric   | Parsed numeric           |

**Note:** Duplicate `mandi_id` values are resolved before dimensional joins to prevent fact-row multiplication.

---

## 6. Standard Units

| Measure     | Standard Unit | Conversion                      |
| ----------- | ------------- | ------------------------------- |
| Quantity    | KG / Qtl      | `1 Qtl = 100 KG`                |
| Quantity    | Tonne         | `1 Tonne = 1,000 KG`            |
| Distance    | KM            | `1 Mile = 1.609344 KM`          |
| Temperature | °C            | Fahrenheit converted to Celsius |
| Rainfall    | mm            | Inches converted to millimetres |

---

## 7. Analytical Join Keys

| Dataset   | Joined With  | Key / Method                                             |
| --------- | ------------ | -------------------------------------------------------- |
| Arrivals  | Mandi Master | `mandi_id`                                               |
| Prices    | Mandi Master | `mandi_id`                                               |
| Transport | Mandi Master | `mandi_id`                                               |
| Weather   | District     | Tracked synthetic sensor→district mapping; no mandi-level attribution                      |
| Arrivals  | Prices       | No forced exact-date join due to sparse temporal overlap |

## Weather attribution
The weather workbook has no district field. DatOps uses `data/weather_sensor_district_map.csv`, a deterministic synthetic sensor→district mapping permitted by the competition notes. Each known sensor maps to one district; multiple sensors may map to a district; `UNKNOWN` sensors are left unattributed. This mapping is not claimed as real-world geography.

## Transport warehouse field
The transport source includes `destination_warehouse`. DatOps preserves this field through cleaning and DuckDB so warehouse-level and mandi→warehouse route performance can be measured. The transport source has no shipment-quantity field, so trip counts are used for inbound activity rather than reported as crop tonnage.
