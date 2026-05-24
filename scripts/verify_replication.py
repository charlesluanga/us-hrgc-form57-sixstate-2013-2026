"""
Verify locked cohort and headline replication statistics (journal / reviewer check).

Run from repository root:
  python scripts/verify_replication.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "all_states.csv"
MANIFEST = ROOT / "data" / "cohort_manifest.json"
RESULTS = ROOT / "outputs" / "revision_results.json"
EXPECTED = ROOT / "expected" / "key_metrics.json"


def _load_y(df: pd.DataFrame) -> pd.Series:
    k = pd.to_numeric(df["Total Killed Form 57"], errors="coerce").fillna(0)
    j = pd.to_numeric(df["Total Injured Form 57"], errors="coerce").fillna(0)
    return ((k >= 1) | (j >= 1)).astype(int)


def main() -> int:
    failed: list[str] = []
    exp = json.loads(EXPECTED.read_text(encoding="utf-8"))

    if not CSV.is_file():
        print(f"MISSING: {CSV}")
        return 1

    df = pd.read_csv(CSV, low_memory=False)
    df["Y"] = _load_y(df)
    n = len(df)
    if n != exp["cohort_n"]:
        failed.append(f"cohort_n: got {n}, expected {exp['cohort_n']}")

    harm_rate = round(float(df["Y"].mean()), 3)
    if harm_rate != exp["harm_rate"]:
        failed.append(f"harm_rate: got {harm_rate}, expected {exp['harm_rate']}")

    if MANIFEST.is_file():
        manifest_n = int(json.loads(MANIFEST.read_text(encoding="utf-8"))["n_rows"])
        if manifest_n != n:
            failed.append(f"manifest n_rows ({manifest_n}) != csv rows ({n})")

    if RESULTS.is_file():
        rev = json.loads(RESULTS.read_text(encoding="utf-8"))
        checks = [
            ("rho_hat", rev["h3_rho_bootstrap"]["k2"]["point"], 3),
            ("rolling_origin_mean_auprc", rev["rolling_origin_balanced"]["mean_auprc"], 3),
            ("cv_with_damage_mean_auprc", rev["cv_full"]["mean_auprc"], 3),
            ("cv_no_damage_mean_auprc", rev["cv_no_damage_cost"]["mean_auprc"], 3),
        ]
        for key, val, nd in checks:
            got = round(float(val), nd)
            want = exp[key]
            if got != want:
                failed.append(f"{key}: got {got}, expected {want}")
    else:
        print(f"Note: {RESULTS.name} not found — run scripts/run_revision_analyses.py first.")

    if failed:
        print("Verification FAILED:")
        for f in failed:
            print(f"  - {f}")
        return 1

    print(f"OK — cohort N={n}, harm rate={harm_rate}, headline metrics match expected/key_metrics.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
