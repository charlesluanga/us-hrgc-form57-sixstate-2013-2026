# Data dictionary — `all_states.csv`

**Rows:** 8,394 incidents  
**States:** California, Georgia, Minnesota, New Jersey, Texas, Wisconsin  
**Dates:** 2013-01-01 through 2026-02-28 (last observed date in this file)

## Outcome fields (Form 57)

| Column | Description |
|--------|-------------|
| `Total Killed Form 57` | Count of fatalities |
| `Total Injured Form 57` | Count of injuries |

**Harm indicator (common derivations):** any row with killed ≥ 1 or injured ≥ 1.

## Identifiers and time

| Column | Description |
|--------|-------------|
| `Global_ID` | Row number in this file (1…N) |
| `Grade Crossing ID` | FRA crossing identifier |
| `Date` | Incident date (ISO) |
| `State Name` | Uppercase state name |

## Exposure / context fields (examples)

| Column | Description |
|--------|-------------|
| `Visibility` | e.g. Dark, Day, Dusk, Dawn |
| `Weather Condition` | Administrative weather label |
| `Roadway Condition` | Road surface / condition label |
| `User Age` | Numeric; **0 recoded to missing** at ingest |
| `Estimated Vehicle Speed` | Numeric when reported |
| `Train Speed` | Numeric when reported |
| `Vehicle Damage Cost` | Numeric; often post-incident |
| `Narrative` | Free text (incident description) |

Full column list: `cohort_manifest.json` → `canonical_columns`.

## Missingness (this file)

| Field | Approx. missing % |
|-------|------------------:|
| User Age | 17.6% |
| Vehicle Damage Cost | 3.6% |
| Visibility, weather, roadway | &lt; 0.02% |

## Repeat crossings (descriptive)

For a given `Grade Crossing ID`, **n** = number of incident rows in this file. Used for repeat-location summaries (e.g. share of harm events where **n ≥ 2** at the same crossing).
