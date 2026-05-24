# File manifest — public GitHub repository

Use this list when uploading to **`us-hrgc-form57-sixstate-2013-2026`**.

Prepared from private workspace: `United States Data/data_sharing/`  
Assembly script: `prepare_github_release.ps1` (copies from private project)

---

## What journals and reviewers typically expect

Transport-safety and epidemiology journals (e.g. **Accident Analysis & Prevention**, **Transportation Research Part A/C**, **Journal of Safety Research**, **PLOS ONE**, **BMJ Open**, Nature portfolio) commonly require:

| Expectation | This repository |
|-------------|-----------------|
| **Analysis code** that reproduces tables/figures | `scripts/run_revision_analyses.py`, figure scripts |
| **Data** or clear access instructions | `data/all_states.csv` + FRA download note in README |
| **Step-by-step README** | `README.md`, `REPRODUCE.md` |
| **Software versions** | `requirements.txt`, `SOFTWARE.md` |
| **Verification** of key results | `expected/key_metrics.json`, `scripts/verify_replication.py` |
| **License** | `LICENSE`, `DATA_LICENSE.md` |
| **Random seeds documented** | README + `SOFTWARE.md` (seed = 42) |

They do **not** need your internal reviewer correspondence, Word drafts, or revision-round scripts.

---

## UPLOAD THESE (public)

### Root

| File | Role |
|------|------|
| `README.md` | Overview + quick start |
| `REPRODUCE.md` | Full replication steps |
| `SOFTWARE.md` | Python version + seeds |
| `LICENSE` | Code license (MIT) |
| `DATA_LICENSE.md` | Data license (CC BY 4.0) |
| `requirements.txt` | Pinned dependencies |
| `.gitignore` | Exclude venv, FRA bulk CSV |
| `FILE_MANIFEST.md` | This file |

### `data/`

| File | Role |
|------|------|
| `all_states.csv` | **Locked analytic cohort (N = 8,394)** — essential |
| `cohort_manifest.json` | Schema, filters, row count |
| `DATA_CHANGELOG.md` | Cohort build history |
| `cleaning_report.txt` | Filter counts |

### `scripts/`

| File | Role |
|------|------|
| `clean_hrgc.py` | Rebuild cohort from FRA Form 57 |
| `run_revision_analyses.py` | **Primary** statistics (H1–H3, CV, rolling-origin) |
| `build_manuscript_figures.py` | Main Figure 2 + Supplementary S1/S2 panels (**run** to create PNG) |
| `run_treeshap_analysis.py` | TreeSHAP (Figure S2d) |
| `build_appendix_figures.py` | Appendix interpretability panels |
| `build_manuscript_tables_excel.py` | Replication tables (Excel) |
| `cv_metrics_io.py` | CV metrics helper |
| `figure_style.py` | Publication matplotlib style |
| `figure_paths.py` | Figure folder naming |
| `label_supplementary_panels.py` | Word-friendly FigureS1/S2 copies |
| `verify_replication.py` | Automated headline checks |

### `expected/`

| File | Role |
|------|------|
| `key_metrics.json` | Target ρ, AUPRC, N, etc. |

### `outputs/` (statistics only — **no figure PNG/PDF**)

| File | Role |
|------|------|
| `revision_results.json` | Full analysis JSON for headline verification |

Reviewers run figure scripts locally; outputs are not committed to GitHub.

---

## Not shared (by design)

| Item | Reason |
|------|--------|
| Conceptual Figure 1 | Author-designed diagram (not code-reproducible) |
| Pre-built figure PNG/PDF | Scripts-only replication policy; avoids stale binaries |
| `build_conceptual_framework_figure.py` | Not applicable to published Figure 1 |

---

## DO NOT UPLOAD (keep private)

| Path | Reason |
|------|--------|
| `manuscript/reviews/` | Reviewer correspondence |
| `manuscript/exports/*.docx`, `*.pdf` | Submission drafts |
| `manuscript/FULL_MANUSCRIPT.md` | Prose (optional: publish post-acceptance) |
| `manuscript/data_sharing_PUBLISH_INSTRUCTIONS.md` | Internal AI/publish notes |
| `manuscript/figures/FIGURE_*_WORD_LAYOUT.md` | Internal Word layout |
| `run_round3_analyses.py`, `run_round4_analyses.py` | Superseded revision rounds |
| `assemble_full_manuscript.py`, `inject_figure_images.py` | Manuscript assembly only |
| `sync_cv_metrics_to_manuscript.py`, `sync_rolling_origin_prose.py` | Prose sync, not statistics |
| `*.pdf` literature files at repo root | Copyright |
| `Highway-Rail_Grade_Crossing_Incident_Data__Form_57_.csv` | Too large; document download |

---

## Suggested GitHub repository tree

```
us-hrgc-form57-sixstate-2013-2026/
├── README.md
├── REPRODUCE.md
├── SOFTWARE.md
├── LICENSE
├── DATA_LICENSE.md
├── requirements.txt
├── .gitignore
├── FILE_MANIFEST.md
├── data/
│   ├── all_states.csv
│   ├── cohort_manifest.json
│   ├── DATA_CHANGELOG.md
│   └── cleaning_report.txt
├── scripts/
│   ├── clean_hrgc.py
│   ├── run_revision_analyses.py
│   ├── build_manuscript_figures.py
│   ├── build_conceptual_framework_figure.py
│   ├── run_treeshap_analysis.py
│   ├── build_appendix_figures.py
│   ├── build_manuscript_tables_excel.py
│   ├── cv_metrics_io.py
│   ├── figure_style.py
│   ├── figure_paths.py
│   ├── label_supplementary_panels.py
│   └── verify_replication.py
├── expected/
│   └── key_metrics.json
└── outputs/
    └── revision_results.json   # statistics only; no figures/
```

---

## Data availability statement (for manuscript)

> Analysis code, the locked six-state analytic cohort (N = 8,394), and verification scripts are available at https://github.com/charlesluanga/us-hrgc-form57-sixstate-2013-2026 (CC BY 4.0 for data; MIT for code). Primary Form 57 records are from the U.S. DOT open-data portal; bulk download instructions are in the repository README.
