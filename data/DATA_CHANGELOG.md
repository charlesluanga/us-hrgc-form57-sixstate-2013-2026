# Data changelog — Form 57 six-state cohort

## 2026-05-17 — FRA open-data CSV ingest (extended window through 2026)

### Source

| Item | Value |
|------|--------|
| **File** | `Highway-Rail_Grade_Crossing_Incident_Data__Form_57_.csv` |
| **Pipeline** | `clean_hrgc.py --source csv` |
| **States** | California, Georgia, Minnesota, New Jersey, Texas, Wisconsin |
| **Date window** | **2013-01-01 → 2026-12-31** (inclusive) |

### Cohort size

| Cohort | N | Notes |
|--------|---|--------|
| **2013–2022 (legacy manuscript lock)** | **6,300** | Same total as prior `all_states.csv`; WI +1 / MN −1 vs 2022-only export |
| **2013–2026 (current analytic file)** | **8,394** | +2,094 incidents after 2022; 3 rows dropped for missing crossing ID |

Harm rate and state-level statistics are logged in `cleaning_report.txt` and `cohort_manifest.json`.

### Schema changes

| Change | Detail |
|--------|--------|
| **Added columns** | `Estimated Vehicle Speed`, `Train Speed`, `Estimated/Recorded Speed` |
| **User Age** | FRA sentinel `0` recoded to **missing** (not treated as age zero) |
| **Global_ID** | Sequential row ID in `all_states.csv` |

### Processing notes

- Ingest uses **State Name** filter on the national export (no Excel sheet quarantine).
- Legacy **449 Georgia/Wisconsin misfiled rows** applied only to the old **Excel** workbook path (`--source xlsx`).
- Exact duplicate rows removed after filters (count in `cleaning_report.txt`).

### Downstream actions required

1. Re-run `manuscript/scripts/build_manuscript_figures.py` and `build_manuscript_tables_excel.py` (hardcoded N=6,300 removed; uses `cohort_manifest.json`).
2. Update manuscript text: **2013–2026**, **N = 8,397**, H2 speed availability, refreshed H3/recurrence metrics.
3. See `manuscript/reviews/REVISION_CHECKLIST_DATA_V2.md` for reviewer-aligned tasks.

---

## 2026-05-09 — Excel workbook ingest (2013–2022 only)

| Item | Value |
|------|--------|
| **Source** | `HRGC_Data.xlsx` (six sheets) |
| **N** | 6,300 |
| **Quarantine** | 449 rows (Georgia sheet, wrong state label) → `quarantined_misfiled_rows.csv` |
| **Speed fields** | Not present |
