"""
Canonical figure directory names under outputs/figures/.
"""
from __future__ import annotations

import shutil
from pathlib import Path

FIG_ROOT = Path(__file__).resolve().parents[1] / "figures"

# Supplementary Figure S1 — diagnostic 3-fold CV (PR, calibration, fold AUPRC)
DIR_S1_DIAGNOSTIC_CV = "Figure_S1_diagnostic_CV"
DIR_S1_LEGACY_CV = "Figure1_CV_performance"  # legacy; same panels as S1

# Supplementary Figure S2 — RF importance, partial dependence, TreeSHAP
DIR_S2_RF_STRUCTURE = "Figure_S2_RF_importance_TreeSHAP"
DIR_S2_LEGACY_RF = "Figure2_RF_global_structure"  # legacy; same panels as S2

# Main-text figures (not supplementary)
DIR_MAIN_CONCEPTUAL = "Figure1_conceptual_framework"
DIR_MAIN_RECURRENCE = "Figure3_recurrence_burden"


def mirror_figure_directory(src: Path, dst: Path) -> int:
    """Copy all PNG/PDF panels from src to dst. Returns number of files copied."""
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for pattern in ("*.png", "*.pdf"):
        for f in src.glob(pattern):
            shutil.copy2(f, dst / f.name)
            n += 1
    return n


def sync_supplementary_aliases(fig_root: Path | None = None) -> dict[str, int]:
    """Mirror legacy CV/RF panel dirs to Figure_S1_* and Figure_S2_* names."""
    root = fig_root or FIG_ROOT
    counts = {
        DIR_S1_DIAGNOSTIC_CV: mirror_figure_directory(
            root / DIR_S1_LEGACY_CV, root / DIR_S1_DIAGNOSTIC_CV
        ),
        DIR_S2_RF_STRUCTURE: mirror_figure_directory(
            root / DIR_S2_LEGACY_RF, root / DIR_S2_RF_STRUCTURE
        ),
    }
    label_supplementary_panels(root)
    return counts


# Word 2×2 panel order — copies with FigureS1a_ / FigureS2a_ prefixes beside originals.
FIGURE_S1_PANELS: list[tuple[str, str, str]] = [
    ("a", "panel_precision_recall_curves_out_of_fold_predictions_stratified_K3", "PR_curves"),
    ("b", "panel_reliability_calibration_three_models_stratified_K3", "calibration"),
    ("c", "panel_crossvalidated_metrics_mean_SD_bars_stratified_K3", "CV_metrics_bars"),
    ("d", "panel_foldwise_AUPRC_three_models_stratified_K3", "foldwise_AUPRC"),
]

# Main-text Figure 2 (folder Figure3_recurrence_burden)
MAIN_FIGURE_2_PANELS: list[tuple[str, str, str]] = [
    (
        "a",
        "panel_cumulative_share_injury_fatality_Y1_crossings_ordered_by_incident_count",
        "Lorenz_concentration",
    ),
    (
        "b",
        "panel_histogram_inter_event_gap_days_repeat_crossings_at_least_two_events",
        "interevent_gap_KDE",
    ),
    (
        "c",
        "panel_stacked_bars_Y1_share_repeat_crossing_vs_single_event_by_state",
        "state_harm_composition",
    ),
    ("d", "panel_annual_incident_counts_all_states", "annual_incident_trend"),
]

FIGURE_S2_PANELS: list[tuple[str, str, str]] = [
    (
        "a",
        "panel_random_forest_variable_importance_top18_Gini_diagnostic_80_20_stratified",
        "RF_variable_importance",
    ),
    ("b", "panel_partial_dependence_random_forest_average_User_Age", "PDP_user_age"),
    ("c", "panel_partial_dependence_random_forest_average_Year", "PDP_year"),
    ("d", "treeshap_mean_abs_bar", "TreeSHAP"),
]


def _write_labeled_copies(
    folder: Path, figure_tag: str, panels: list[tuple[str, str, str]]
) -> int:
    """Copy each panel to FigureS2a_shortname.png (and .pdf) for Word layout."""
    if not folder.is_dir():
        return 0
    n = 0
    for letter, stem, short in panels:
        for ext in ("png", "pdf"):
            src = folder / f"{stem}.{ext}"
            if not src.is_file():
                continue
            dst = folder / f"{figure_tag}{letter}_{short}.{ext}"
            shutil.copy2(src, dst)
            n += 1
    return n


def label_main_figure_2_panels(fig_root: Path | None = None) -> int:
    """Figure2a_… copies for main-text Figure 2 (recurrence burden)."""
    root = fig_root or FIG_ROOT
    return _write_labeled_copies(root / DIR_MAIN_RECURRENCE, "Figure2", MAIN_FIGURE_2_PANELS)


def label_supplementary_panels(fig_root: Path | None = None) -> dict[str, int]:
    """Add FigureS1a_ / FigureS2a_ labeled copies in legacy and S-prefixed folders."""
    root = fig_root or FIG_ROOT
    out: dict[str, int] = {}
    for legacy, sdir, tag, panels in (
        (DIR_S1_LEGACY_CV, DIR_S1_DIAGNOSTIC_CV, "FigureS1", FIGURE_S1_PANELS),
        (DIR_S2_LEGACY_RF, DIR_S2_RF_STRUCTURE, "FigureS2", FIGURE_S2_PANELS),
    ):
        out[f"{legacy}_labeled"] = _write_labeled_copies(root / legacy, tag, panels)
        out[f"{sdir}_labeled"] = _write_labeled_copies(root / sdir, tag, panels)
    return out

