"""Verify shipped data/all_states.csv matches expected checksums and row counts."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "all_states.csv"
EXPECTED = REPO / "expected" / "cohort_checksums.json"


def main() -> int:
    if not DATA.is_file():
        print(f"Missing {DATA}", file=sys.stderr)
        return 1
    exp = json.loads(EXPECTED.read_text(encoding="utf-8"))
    sha = hashlib.sha256(DATA.read_bytes()).hexdigest()
    if sha != exp["sha256_all_states_csv"]:
        print("FAIL: SHA-256 mismatch for all_states.csv")
        return 1

    df = pd.read_csv(DATA, low_memory=False)
    k = df["Total Killed Form 57"].fillna(0)
    j = df["Total Injured Form 57"].fillna(0)
    y = ((k >= 1) | (j >= 1)).astype(int)
    gid = df.groupby("Grade Crossing ID").size()
    repeat_share = float(y[df["Grade Crossing ID"].map(gid) >= 2].sum() / y.sum())

    checks = [
        ("n_rows", len(df), exp["n_rows"]),
        ("harm_rate_any_injury_or_fatality", round(float(y.mean()), 4), exp["harm_rate_any_injury_or_fatality"]),
        (
            "share_harm_where_crossing_incident_count_ge_2",
            round(repeat_share, 4),
            exp["share_harm_where_crossing_incident_count_ge_2"],
        ),
    ]
    ok = True
    for name, got, want in checks:
        if got != want:
            print(f"FAIL {name}: got {got}, expected {want}")
            ok = False
        else:
            print(f"OK   {name}: {got}")
    print("OK   sha256_all_states_csv")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
