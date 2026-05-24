"""Repository paths for public replication package (data_sharing layout)."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "outputs"
FIGURES_DIR = OUTPUT_DIR / "figures"

CSV = DATA_DIR / "all_states.csv"
COHORT_MANIFEST = DATA_DIR / "cohort_manifest.json"
REVISION_RESULTS = OUTPUT_DIR / "revision_results.json"
CV_METRICS_JSON = FIGURES_DIR / "figure_cv_metrics.json"

for p in (DATA_DIR, OUTPUT_DIR, FIGURES_DIR):
    p.mkdir(parents=True, exist_ok=True)
