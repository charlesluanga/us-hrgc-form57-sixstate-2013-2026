"""
Shared CV metrics for Figure 1 / Section 4.2 / Excel Table 7.

- build_manuscript_figures.py writes outputs/figures/figure_cv_metrics.json
- build_manuscript_tables_excel.py reads it for Table7_Figure1_CV
- sync_cv_metrics_to_manuscript.py refreshes delimited blocks in markdown
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIG_METRICS_JSON = ROOT / "manuscript" / "figures" / "figure_cv_metrics.json"

MARK_BEGIN_PANEL_C = "<!-- AUTO_CV_S42_PANEL_C -->"
MARK_END_PANEL_C = "<!-- END_AUTO_CV_S42_PANEL_C -->"
MARK_BEGIN_ACROSS = "<!-- AUTO_CV_S42_ACROSS_FOLDS -->"
MARK_END_ACROSS = "<!-- END_AUTO_CV_S42_ACROSS_FOLDS -->"


def write_cv_metrics_json(summary: dict[str, Any]) -> None:
    """Persist fold-mean metrics from cv_oof_and_fold_metrics _summary."""
    payload: dict[str, Any] = {
        "schema": "figure_cv_metrics.v1",
        "models": {},
    }
    for key in ("hgb", "rf", "lr"):
        s = summary[key]
        payload["models"][key] = {
            "mean_auprc": float(s["mean_auprc"]),
            "sd_auprc": float(s["sd_auprc"]),
            "mean_auroc": float(s["mean_auroc"]),
            "sd_auroc": float(s["sd_auroc"]),
            "mean_brier": float(s["mean_brier"]),
            "sd_brier": float(s["sd_brier"]),
            "mean_log_loss": float(s["mean_ll"]),
            "sd_log_loss": float(s["sd_ll"]),
        }
    FIG_METRICS_JSON.parent.mkdir(parents=True, exist_ok=True)
    FIG_METRICS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_cv_models() -> dict[str, dict[str, float]]:
    if not FIG_METRICS_JSON.is_file():
        raise FileNotFoundError(
            f"Missing {FIG_METRICS_JSON}. Run: python manuscript/scripts/build_manuscript_figures.py"
        )
    data = json.loads(FIG_METRICS_JSON.read_text(encoding="utf-8"))
    if data.get("schema") != "figure_cv_metrics.v1" or "models" not in data:
        raise ValueError(f"Unexpected JSON schema in {FIG_METRICS_JSON}")
    return data["models"]


def cv_rows_for_excel() -> list[dict[str, Any]]:
    """Rows for openpyxl Table 7 (numeric cells; number_format 0.000 in sheet)."""
    m = load_cv_models()
    rows = [
        {
            "Model": "HistGradientBoostingClassifier (sklearn)",
            "Mean_AUPRC": m["hgb"]["mean_auprc"],
            "SD_AUPRC": m["hgb"]["sd_auprc"],
            "Mean_AUROC": m["hgb"]["mean_auroc"],
            "SD_AUROC": m["hgb"]["sd_auroc"],
            "Mean_Brier": m["hgb"]["mean_brier"],
            "SD_Brier": m["hgb"]["sd_brier"],
            "Mean_log_loss": m["hgb"]["mean_log_loss"],
            "SD_log_loss": m["hgb"]["sd_log_loss"],
        },
        {
            "Model": "RandomForestClassifier (sklearn)",
            "Mean_AUPRC": m["rf"]["mean_auprc"],
            "SD_AUPRC": m["rf"]["sd_auprc"],
            "Mean_AUROC": m["rf"]["mean_auroc"],
            "SD_AUROC": m["rf"]["sd_auroc"],
            "Mean_Brier": m["rf"]["mean_brier"],
            "SD_Brier": m["rf"]["sd_brier"],
            "Mean_log_loss": m["rf"]["mean_log_loss"],
            "SD_log_loss": m["rf"]["sd_log_loss"],
        },
        {
            "Model": "LogisticRegression L2 liblinear, class_weight balanced",
            "Mean_AUPRC": m["lr"]["mean_auprc"],
            "SD_AUPRC": m["lr"]["sd_auprc"],
            "Mean_AUROC": m["lr"]["mean_auroc"],
            "SD_AUROC": m["lr"]["sd_auroc"],
            "Mean_Brier": m["lr"]["mean_brier"],
            "SD_Brier": m["lr"]["sd_brier"],
            "Mean_log_loss": m["lr"]["mean_log_loss"],
            "SD_log_loss": m["lr"]["sd_log_loss"],
        },
    ]
    return rows


def _f3(x: float) -> str:
    return f"{float(x):.3f}"


def _fmt_sd(x: float) -> str:
    """SDs can be small; use up to 4 decimals and trim trailing zeros."""
    s = f"{float(x):.4f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def format_panel_c_markdown() -> str:
    m = load_cv_models()
    h, r, l = m["hgb"], m["rf"], m["lr"]
    return (
        "**Panel C** reports fold-averaged **AUPRC**, **AUROC**, **Brier score**, and **log-loss** "
        "(mean ± SD across folds), numerically aligned with **`outputs/figures/figure_cv_metrics.json`** "
        "(and **`figure_cv_metrics.txt`**) from **`scripts/build_manuscript_figures.py`**. "
        f"**Histgradient boosting**: mean **AUPRC {_f3(h['mean_auprc'])}** (SD **{_fmt_sd(h['sd_auprc'])}**), "
        f"mean **AUROC {_f3(h['mean_auroc'])}** (SD **{_fmt_sd(h['sd_auroc'])}**), "
        f"mean **Brier {_f3(h['mean_brier'])}** (SD **{_fmt_sd(h['sd_brier'])}**), "
        f"mean **log-loss {_f3(h['mean_log_loss'])}** (SD **{_fmt_sd(h['sd_log_loss'])}**). "
        f"**Random forest**: mean **AUPRC {_f3(r['mean_auprc'])}** (SD **{_fmt_sd(r['sd_auprc'])}**), "
        f"mean **AUROC {_f3(r['mean_auroc'])}** (SD **{_fmt_sd(r['sd_auroc'])}**), "
        f"mean **Brier {_f3(r['mean_brier'])}** (SD **{_fmt_sd(r['sd_brier'])}**), "
        f"mean **log-loss {_f3(r['mean_log_loss'])}** (SD **{_fmt_sd(r['sd_log_loss'])}**). "
        "**L2** logistic regression (**`sklearn`**, **`liblinear`**, **`class_weight='balanced'`** on sparse one-hot): "
        f"mean **AUPRC {_f3(l['mean_auprc'])}** (SD **{_fmt_sd(l['sd_auprc'])}**), "
        f"mean **AUROC {_f3(l['mean_auroc'])}** (SD **{_fmt_sd(l['sd_auroc'])}**), "
        f"mean **Brier {_f3(l['mean_brier'])}** (SD **{_fmt_sd(l['sd_brier'])}**), "
        f"mean **log-loss {_f3(l['mean_log_loss'])}** (SD **{_fmt_sd(l['sd_log_loss'])}**)."
    )


def format_across_folds_markdown() -> str:
    m = load_cv_models()
    h, r = m["hgb"], m["rf"]
    gap = abs(float(r["mean_auprc"]) - float(h["mean_auprc"]))
    gap_s = f"{gap:.4f}".rstrip("0").rstrip(".")
    if r["mean_auprc"] >= h["mean_auprc"]:
        auprc_line = (
            f"Across folds, mean **AUPRC** was **{gap_s}** lower for **histgradient boosting** "
            f"than for **random forest** (**{_f3(h['mean_auprc'])}** versus **{_f3(r['mean_auprc'])}**)."
        )
    else:
        auprc_line = (
            f"Across folds, mean **AUPRC** was **{gap_s}** lower for **random forest** "
            f"than for **histgradient boosting** (**{_f3(r['mean_auprc'])}** versus **{_f3(h['mean_auprc'])}**)."
        )

    order = sorted(
        [
            ("rf", "**random forest**", m["rf"]["mean_log_loss"]),
            ("hgb", "**histgradient boosting**", m["hgb"]["mean_log_loss"]),
            ("lr", "**L2** logistic", m["lr"]["mean_log_loss"]),
        ],
        key=lambda t: t[2],
    )
    d0, lab0, v0 = order[0]
    d1, lab1, v1 = order[1]
    d2, lab2, v2 = order[2]
    _ = (d0, d1, d2)
    ll_line = (
        f"Mean **log-loss** was lowest for {lab0} (**{_f3(v0)}**), followed by {lab1} (**{_f3(v1)}**), "
        f"then {lab2} (**{_f3(v2)}**)."
    )
    return f"{auprc_line} {ll_line}"


def replace_marked_region(text: str, begin: str, end: str, inner: str) -> str:
    if begin not in text:
        raise ValueError(f"Missing begin marker {begin!r}")
    if end not in text:
        raise ValueError(f"Missing end marker {end!r}")
    i0 = text.index(begin) + len(begin)
    if i0 < len(text) and text[i0] == "\n":
        i0 += 1
    i1 = text.index(end)
    if i1 < i0:
        raise ValueError("End marker appears before begin content")
    return text[:i0] + inner.strip() + "\n" + text[i1:]


def sync_markdown_files(paths: list[Path]) -> None:
    panel_c = format_panel_c_markdown()
    across = format_across_folds_markdown()
    for path in paths:
        raw = path.read_text(encoding="utf-8")
        raw2 = replace_marked_region(raw, MARK_BEGIN_PANEL_C, MARK_END_PANEL_C, panel_c)
        raw3 = replace_marked_region(raw2, MARK_BEGIN_ACROSS, MARK_END_ACROSS, across)
        path.write_text(raw3, encoding="utf-8")

