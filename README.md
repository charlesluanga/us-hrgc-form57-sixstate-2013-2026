# Six-state FRA Form 57 analytic cohort and replication code

Public materials for reproducing the locked **N = 8,394** six-state highway–rail grade crossing (HRGC) incident cohort and headline statistical results.
**Repository:** `https://github.com/charlesluanga/us-hrgc-form57-sixstate-2013-2026`

## What this repository contains

| Component | Purpose |
|-----------|---------|
| `data/all_states.csv` | Locked analytic incident file (study states, 2013–2026 window) |
| `data/cohort_manifest.json` | Row count, filters, column schema |
| `scripts/clean_hrgc.py` | Rebuild cohort from U.S. DOT open Form 57 CSV |
| `scripts/run_revision_analyses.py` | Primary analyses (H1–H3, rolling-origin CV, sensitivities) |
| `scripts/build_manuscript_figures.py` | Main Figure 2 + Supplementary S1/S2 (run scripts to generate PNG panels) |
| `scripts/run_treeshap_analysis.py` | TreeSHAP (Supplementary Figure S2d) |
| `outputs/revision_results.json` | Precomputed headline statistics (optional verify without full re-run) |
| `expected/key_metrics.json` | Headline numbers for automated verification |



## Quick start 

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

python scripts/verify_replication.py
```

Expected: `OK — cohort N=8394, harm rate=0.391, …`

## Full reproduction

```bash
# 1. Optional: rebuild cohort from FRA open data (place CSV in repo root; see below)
python scripts/clean_hrgc.py --source csv

# 2. Primary analyses → outputs/revision_results.json
python scripts/run_revision_analyses.py

# 3. Figures (optional) → outputs/figures/*.png — run locally; not stored in repo
python scripts/build_manuscript_figures.py
python scripts/run_treeshap_analysis.py

# 4. Verify headline statistics
python scripts/verify_replication.py
```

See **`REPRODUCE.md`** for the full checklist and expected outputs.

## Data source

| Item | Detail |
|------|--------|
| Source | U.S. DOT open-data **Form 57** export |
| File | `Highway-Rail_Grade_Crossing_Incident_Data__Form_57_.csv` |
| Download | [U.S. DOT open data portal](https://data.transportation.gov/) — search “Form 57” |
| Study states | California, Georgia, Minnesota, New Jersey, Texas, Wisconsin |
| Date window | 2013-01-01 through last observed date in download (2026 partial year in locked cohort) |

The bulk FRA file is **not** stored in this repository (size). Either use the provided `data/all_states.csv` or download Form 57 and run `clean_hrgc.py`.

## Random seed

All stochastic steps use **`random_state = 42`** (stratified CV, random forest, histgradient boosting, bootstrap draws).

## Software

Python **3.12.x**; pinned packages in `requirements.txt`. See `SOFTWARE.md`.

## License

Code and documentation: **MIT License** (`LICENSE`).  
Analytic data file: **CC BY 4.0** (see `DATA_LICENSE.md`).

## Citation

Cite the peer-reviewed article when available. Until publication, cite this repository:

> Luanga, C. (2026). *U.S. six-state FRA Form 57 HRGC analytic cohort and replication scripts* (Version 1.0). GitHub. https://github.com/charlesluanga/us-hrgc-form57-sixstate-2013-2026

## Contact

Open a GitHub issue for replication questions.
