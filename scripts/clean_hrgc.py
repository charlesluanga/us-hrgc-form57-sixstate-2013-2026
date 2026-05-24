"""
Clean HRGC (Highway-Rail Grade Crossing) Form 57 data and export study-state CSVs.

Primary input (default): U.S. DOT open-data Form 57 CSV export.
Legacy input: six-state Excel workbook (HRGC_Data.xlsx).

Outputs (csv/):
  <State>.csv                  — one per study state, canonical schema
  all_states.csv               — combined analytic cohort
  quarantined_misfiled_rows.csv — legacy Excel only (wrong State Name on sheet)
  cohort_manifest.json         — N, date window, column list (for downstream scripts)
  cleaning_report.txt
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC_CSV = ROOT / "Highway-Rail_Grade_Crossing_Incident_Data__Form_57_.csv"
SRC_XLSX = Path(r"C:\Users\User\OneDrive\Documents\United States Data, HRGC_Data.xlsx")
OUT_DIR = ROOT / "data"

DATE_START = pd.Timestamp("2013-01-01")
DATE_END = pd.Timestamp("2026-12-31")

STUDY_STATES = [
    "CALIFORNIA",
    "GEORGIA",
    "MINNESOTA",
    "NEW JERSEY",
    "TEXAS",
    "WISCONSIN",
]

REPORT_LINES: list[str] = []

# Columns present in per-state / combined exports (canonical + speed from FRA export).
CANONICAL_COLUMNS = [
    "S.No",
    "Report Year",
    "Incident Number",
    "Grade Crossing ID",
    "Date",
    "AM/PM",
    "Time",
    "County Code",
    "County Name",
    "State Code",
    "State Name",
    "Highway User",
    "Vehicle Direction Code",
    "Vehicle Direction",
    "Highway User Position Code",
    "Highway User Position",
    "Second Highway User",
    "Second Vehicle Direction Code",
    "Second Vehicle Direction",
    "Temperature",
    "Visibility Code",
    "Visibility",
    "Weather Condition Code",
    "Weather Condition",
    "Track Type Code",
    "Track Type",
    "Crossing Warning Expanded 1",
    "Crossing Warning Expanded 2",
    "Crossing Warning Expanded 3",
    "Crossing Warning Expanded 4",
    "Crossing Warning Expanded 5",
    "Crossing Warning Expanded 6",
    "Crossing Warning Expanded 7",
    "Roadway Condition",
    "Crossing Warning Location Code",
    "Crossing Warning Location",
    "User Age",
    "User Sex",
    "Highway User Action Code",
    "Highway User Action",
    "Estimated Vehicle Speed",
    "Train Speed",
    "Estimated/Recorded Speed",
    "Vehicle Damage Cost",
    "Narrative",
    "Total Killed Form 57",
    "Total Injured Form 57",
]

# Direct rename from FRA open-data column names (identity for most fields).
FRA_COLUMN_MAP: dict[str, str] = {
    "Roadway Condition": "Roadway Condition",
}


def log(msg: str = "") -> None:
    print(msg)
    REPORT_LINES.append(msg)


def strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        if df[c].dtype == "object":
            df[c] = df[c].map(lambda v: v.strip() if isinstance(v, str) else v)
    return df


def normalize_time(v):
    if pd.isna(v):
        return np.nan
    if isinstance(v, str):
        return v.strip()
    if hasattr(v, "strftime"):
        try:
            return v.strftime("%H:%M:%S")
        except Exception:
            return str(v)
    return str(v)


def excel_serial_to_date(v):
    if pd.isna(v):
        return pd.NaT
    try:
        return pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(v))
    except Exception:
        return pd.NaT


def recode_user_age(series: pd.Series) -> pd.Series:
    """FRA export uses 0.0 as unknown age; convert to missing for modeling."""
    out = pd.to_numeric(series, errors="coerce")
    out = out.mask(out == 0)
    return out


def conform_to_canonical(df: pd.DataFrame, label: str) -> pd.DataFrame:
    extras = [c for c in df.columns if c not in CANONICAL_COLUMNS]
    if extras:
        log(f"  - note: dropped non-canonical columns from {label!r}: {extras[:8]}{'...' if len(extras) > 8 else ''}")
    for c in CANONICAL_COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    return df[CANONICAL_COLUMNS]


def apply_cohort_filters(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Study states and calendar window; require ID, date, and outcome fields."""
    stats: dict[str, int] = {"rows_in": len(df)}

    df["State Name"] = df["State Name"].astype(str).str.strip().str.upper()
    mask_state = df["State Name"].isin(STUDY_STATES)
    stats["excluded_non_study_state"] = int((~mask_state).sum())
    df = df.loc[mask_state].copy()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    mask_date = df["Date"].notna() & (df["Date"] >= DATE_START) & (df["Date"] <= DATE_END)
    stats["excluded_outside_date_window"] = int((~mask_date).sum())
    df = df.loc[mask_date].copy()

    gid = df["Grade Crossing ID"]
    mask_id = gid.notna() & (gid.astype(str).str.strip() != "")
    stats["excluded_missing_crossing_id"] = int((~mask_id).sum())
    df = df.loc[mask_id].copy()

    for col in ("Total Killed Form 57", "Total Injured Form 57"):
        if col not in df.columns:
            df[col] = np.nan
    mask_outcome = df["Total Killed Form 57"].notna() | df["Total Injured Form 57"].notna()
    stats["excluded_missing_outcome_fields"] = int((~mask_outcome).sum())
    df = df.loc[mask_outcome].copy()

    stats["rows_out"] = len(df)
    return df, stats


def load_fra_csv(path: Path) -> pd.DataFrame:
    log(f"Reading FRA CSV: {path}")
    df = pd.read_csv(path, low_memory=False)
    log(f"  - raw rows: {len(df):,}, columns: {len(df.columns)}")
    df = strip_strings(df)
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
    df = df.rename(columns=FRA_COLUMN_MAP)

    if "Time" in df.columns:
        df["Time"] = df["Time"].map(normalize_time)
    if "User Age" in df.columns:
        n_zero = (pd.to_numeric(df["User Age"], errors="coerce") == 0).sum()
        df["User Age"] = recode_user_age(df["User Age"])
        log(f"  - User Age: recoded {n_zero:,} zero values -> missing")

    for speed_col in ("Estimated Vehicle Speed", "Train Speed", "Estimated/Recorded Speed"):
        if speed_col in df.columns:
            df[speed_col] = pd.to_numeric(df[speed_col], errors="coerce")

    return df


def clean_california(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "Highway User.1": "Second Highway User",
        "Vehicle Direction Code.1": "Second Vehicle Direction Code",
        "Vehicle Direction.1": "Second Vehicle Direction",
    }
    present = {k: v for k, v in rename_map.items() if k in df.columns}
    if present:
        df = df.rename(columns=present)
        log(f"  - renamed duplicate columns: {present}")
    return df


def clean_new_jersey(df: pd.DataFrame) -> pd.DataFrame:
    if "Date.1" in df.columns:
        if "Date" in df.columns:
            df = df.drop(columns=["Date"])
        df = df.rename(columns={"Date.1": "Date"})
        log("  - New Jersey: kept parsed Date column")
    return df


def process_excel(src: Path) -> tuple[dict[str, pd.DataFrame], list[pd.DataFrame]]:
    log(f"Source workbook: {src}")
    xl = pd.ExcelFile(src, engine="openpyxl")
    cleaned: dict[str, pd.DataFrame] = {}
    quarantined_frames: list[pd.DataFrame] = []

    for raw_sheet_name in xl.sheet_names:
        sheet_name = raw_sheet_name.strip()
        log(f"\n{'#' * 70}\n# Sheet: {sheet_name!r}\n{'#' * 70}")
        df = pd.read_excel(src, sheet_name=raw_sheet_name, engine="openpyxl")
        log(f"  - rows read: {len(df)}")
        df = strip_strings(df)
        df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]

        if sheet_name.lower() == "california":
            df = clean_california(df)
        elif sheet_name.lower() == "new jersey":
            df = clean_new_jersey(df)

        if "Time" in df.columns:
            df["Time"] = df["Time"].map(normalize_time)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        if "State Name" in df.columns:
            expected = sheet_name.upper()
            wrong = df["State Name"].astype(str).str.strip().str.upper() != expected
            n_wrong = int(wrong.sum())
            if n_wrong:
                bad = df.loc[wrong].copy()
                bad.insert(0, "_source_sheet", sheet_name)
                quarantined_frames.append(bad)
                df = df.loc[~wrong].copy()
                log(f"  - QUARANTINE: {n_wrong} rows with State Name != {expected!r}")

        before = len(df)
        df = df.drop_duplicates().reset_index(drop=True)
        if before != len(df):
            log(f"  - removed {before - len(df)} duplicate row(s)")

        df = conform_to_canonical(df, sheet_name)
        df["S.No"] = range(1, len(df) + 1)
        cleaned[sheet_name] = df
        log(f"  - shape after canonical: {df.shape}")

    return cleaned, quarantined_frames


def finalize_state_frames(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split combined cohort into per-state files."""
    out: dict[str, pd.DataFrame] = {}
    for state in STUDY_STATES:
        sub = df.loc[df["State Name"] == state].copy()
        sub["S.No"] = range(1, len(sub) + 1)
        out[state.title()] = sub
    return out


def write_outputs(
    combined: pd.DataFrame,
    cleaned_by_state: dict[str, pd.DataFrame],
    quarantined_frames: list[pd.DataFrame],
    source_label: str,
    filter_stats: dict[str, int],
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for sheet_name, df in cleaned_by_state.items():
        path = OUT_DIR / f"{sheet_name.replace(' ', '_')}.csv"
        df.to_csv(path, index=False)
        log(f"  - wrote {path.name} ({len(df)} rows)")

    if quarantined_frames:
        q = pd.concat(quarantined_frames, ignore_index=True)
        for c in CANONICAL_COLUMNS:
            if c not in q.columns:
                q[c] = pd.NA
        q = q[["_source_sheet"] + CANONICAL_COLUMNS]
        q_path = OUT_DIR / "quarantined_misfiled_rows.csv"
        q.to_csv(q_path, index=False)
        log(f"\nWrote quarantined rows: {q_path} ({len(q)} rows)")
    else:
        q_path = OUT_DIR / "quarantined_misfiled_rows.csv"
        if q_path.exists():
            q_path.unlink()
        log("\nNo quarantined rows (FRA CSV ingest filters by State Name only).")

    combined = combined.copy()
    combined.insert(0, "Global_ID", range(1, len(combined) + 1))
    combined_path = OUT_DIR / "all_states.csv"
    combined.to_csv(combined_path, index=False)
    log(f"\nWrote combined: {combined_path} (rows={len(combined):,}, cols={combined.shape[1]})")
    log("\nRow counts per state:")
    log(combined.groupby("State Name").size().to_string())

    harm = (combined["Total Killed Form 57"].fillna(0) >= 1) | (
        combined["Total Injured Form 57"].fillna(0) >= 1
    )
    log(f"\nHarm rate (Y=1): {harm.mean():.4f} ({int(harm.sum()):,} / {len(combined):,})")
    log(f"Date range: {combined['Date'].min().date()} to {combined['Date'].max().date()}")

    manifest = {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "source": source_label,
        "date_start": str(DATE_START.date()),
        "date_end": str(DATE_END.date()),
        "study_states": STUDY_STATES,
        "n_rows": int(len(combined)),
        "n_columns": int(combined.shape[1]),
        "canonical_columns": CANONICAL_COLUMNS,
        "filter_stats": filter_stats,
        "legacy_cohort_2013_2022_n": 6300,
    }
    manifest_path = OUT_DIR / "cohort_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log(f"\nWrote manifest: {manifest_path}")


def run_csv_ingest(src: Path) -> None:
    df = load_fra_csv(src)
    df, stats = apply_cohort_filters(df)

    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    stats["exact_duplicates_removed"] = before - len(df)

    df = conform_to_canonical(df, "FRA CSV cohort")
    df["S.No"] = range(1, len(df) + 1)
    cleaned_by_state = finalize_state_frames(df)
    write_outputs(df, cleaned_by_state, [], str(src), stats)


def run_excel_ingest(src: Path) -> None:
    cleaned, quarantined = process_excel(src)
    combined = pd.concat(cleaned.values(), ignore_index=True)
    combined["Date"] = pd.to_datetime(combined["Date"], errors="coerce")
    combined, stats = apply_cohort_filters(combined)
    combined["S.No"] = range(1, len(combined) + 1)
    cleaned_by_state = finalize_state_frames(combined)
    write_outputs(combined, cleaned_by_state, quarantined, str(src), stats)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean HRGC Form 57 data for six-state cohort.")
    parser.add_argument(
        "--source",
        choices=("csv", "xlsx"),
        default="csv",
        help="Input type: FRA open-data CSV (default) or legacy Excel workbook.",
    )
    parser.add_argument("--csv", type=Path, default=SRC_CSV, help="Path to FRA Form 57 CSV.")
    parser.add_argument("--xlsx", type=Path, default=SRC_XLSX, help="Path to legacy Excel workbook.")
    parser.add_argument(
        "--date-end",
        default="2026-12-31",
        help="Inclusive end date for cohort (default: 2026-12-31).",
    )
    args = parser.parse_args()

    global DATE_END
    DATE_END = pd.Timestamp(args.date_end)

    log(f"Output directory: {OUT_DIR}")
    log(f"Run timestamp   : {datetime.now().isoformat(timespec='seconds')}")
    log(f"Study states    : {', '.join(STUDY_STATES)}")
    log(f"Date window     : {DATE_START.date()} to {DATE_END.date()}")
    log("=" * 80)

    if args.source == "csv":
        if not args.csv.exists():
            raise FileNotFoundError(f"CSV not found: {args.csv}")
        run_csv_ingest(args.csv)
    else:
        if not args.xlsx.exists():
            raise FileNotFoundError(f"Excel workbook not found: {args.xlsx}")
        run_excel_ingest(args.xlsx)

    report_path = OUT_DIR / "cleaning_report.txt"
    report_path.write_text("\n".join(REPORT_LINES), encoding="utf-8")
    print(f"\nReport written to: {report_path}")


if __name__ == "__main__":
    main()

