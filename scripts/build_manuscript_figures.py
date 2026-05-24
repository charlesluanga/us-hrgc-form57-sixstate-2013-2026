"""
Generate manuscript Figure 1–3 panels from locked analytic file (csv/all_states.csv).
Methods alignment: Section 3.4 (core x), 3.6–3.7 (diagnostic 3-fold CV; 80/20 for RF diagnostics).

Outputs: each panel saved separately as PNG + PDF under outputs/figures/ (not exports/).
  Supplementary Figure S1: Figure_S1_diagnostic_CV/ (mirrored from Figure1_CV_performance/)
  Supplementary Figure S2: Figure_S2_RF_importance_TreeSHAP/ (mirrored from Figure2_RF_global_structure/)
  Legacy build dirs Figure1_CV_performance/, Figure2_RF_global_structure/ remain the write targets.
    one two-feature PDP strip for Temperature and Year — even count for 2×2 slide layouts)
  outputs/figures/Figure3_recurrence_burden/...
  outputs/figures/figure_cv_metrics.txt
  outputs/figures/figure_cv_metrics.json (machine-readable; drives §4.2 sync and Excel Table 7)

Journal-style: Times New Roman, high-resolution raster (600 dpi PNG), vector PDF,
no in-figure titles (captions and panel letters belong in the manuscript or slides).

The linear panel uses sparse one-hot + LogisticRegression(solver="liblinear", class_weight="balanced").
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import PartialDependenceDisplay
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from cv_metrics_io import write_cv_metrics_json
from figure_style import FIG_SIZE, PALETTE, SAVE_DPI, apply_publication_rc, new_panel, save_figure, style_axes
from figure_paths import (
    DIR_S1_DIAGNOSTIC_CV,
    DIR_S1_LEGACY_CV,
    DIR_S2_LEGACY_RF,
    DIR_S2_RF_STRUCTURE,
    MAIN_FIGURE_2_PANELS,
    DIR_MAIN_RECURRENCE,
    label_main_figure_2_panels,
    sync_supplementary_aliases,
)

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "all_states.csv"
COHORT_MANIFEST_PATH = ROOT / "data" / "cohort_manifest.json"
FIG_ROOT = ROOT / "outputs" / "figures"


def expected_cohort_n() -> int:
    if COHORT_MANIFEST_PATH.is_file():
        import json

        return int(json.loads(COHORT_MANIFEST_PATH.read_text(encoding="utf-8"))["n_rows"])
    return len(pd.read_csv(CSV_PATH, usecols=["Global_ID"]))

RANDOM_STATE = 42
CV_SEED = 42
N_SPLITS = 3
CAT_COLS = [
    "State Name",
    "Visibility",
    "Weather Condition",
    "Roadway Condition",
    "Track Type",
    "Highway User",
    "Highway User Position",
]
NUM_COLS = ["Year", "Temperature", "Vehicle Damage Cost", "User Age"]

COLORS = {
    "hgb": "#0072B2",
    "rf": "#D55E00",
    "lr": "#009E73",
}


def load_frame() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    df["Year"] = pd.to_datetime(df["Date"], errors="coerce").dt.year
    k = pd.to_numeric(df["Total Killed Form 57"], errors="coerce").fillna(0)
    j = pd.to_numeric(df["Total Injured Form 57"], errors="coerce").fillna(0)
    df["Y"] = ((k >= 1) | (j >= 1)).astype(int)
    return df


def make_Xy(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    X = df[CAT_COLS + NUM_COLS].copy()
    y = df["Y"].values
    return X, y


def make_preprocessor(*, sparse: bool) -> ColumnTransformer:
    cat_pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="constant", fill_value="missing")),
            ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=sparse)),
        ]
    )
    return ColumnTransformer(
        [
            ("cat", cat_pipe, CAT_COLS),
            ("num", SimpleImputer(strategy="median"), NUM_COLS),
        ]
    )


def build_models() -> dict[str, Pipeline]:
    pre = make_preprocessor(sparse=False)
    hgb = Pipeline(
        [
            ("pre", pre),
            (
                "m",
                HistGradientBoostingClassifier(
                    max_iter=120,
                    learning_rate=0.12,
                    max_depth=8,
                    min_samples_leaf=20,
                    l2_regularization=0.15,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    pre_rf = make_preprocessor(sparse=False)
    rf = Pipeline(
        [
            ("pre", pre_rf),
            (
                "m",
                RandomForestClassifier(
                    n_estimators=120,
                    max_depth=16,
                    min_samples_leaf=4,
                    class_weight="balanced_subsample",
                    random_state=RANDOM_STATE,
                    n_jobs=1,
                ),
            ),
        ]
    )
    pre_lr = make_preprocessor(sparse=True)
    lr = Pipeline(
        [
            ("pre", pre_lr),
            (
                "m",
                LogisticRegression(
                    solver="liblinear",
                    penalty="l2",
                    C=1.0,
                    class_weight="balanced",
                    max_iter=200,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    return {"hgb": hgb, "rf": rf, "lr": lr}


def cv_oof_and_fold_metrics(
    X: pd.DataFrame, y: np.ndarray, models: dict[str, Pipeline]
) -> dict:
    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=CV_SEED)
    out: dict = {k: {"oof": np.zeros(len(y)), "fold_auprc": []} for k in models}
    metrics = {k: {"auprc": [], "auroc": [], "brier": [], "ll": []} for k in models}

    for _fold_idx, (tr, va) in enumerate(cv.split(X, y)):
        X_tr, X_va = X.iloc[tr], X.iloc[va]
        y_tr, y_va = y[tr], y[va]
        for name, pipe in models.items():
            est = clone(pipe)
            est.fit(X_tr, y_tr)
            p = est.predict_proba(X_va)[:, 1]
            out[name]["oof"][va] = p
            metrics[name]["auprc"].append(average_precision_score(y_va, p))
            metrics[name]["auroc"].append(roc_auc_score(y_va, p))
            metrics[name]["brier"].append(brier_score_loss(y_va, p))
            metrics[name]["ll"].append(log_loss(y_va, p))

    summary = {}
    for name in models:
        summary[name] = {
            "mean_auprc": float(np.mean(metrics[name]["auprc"])),
            "sd_auprc": float(np.std(metrics[name]["auprc"], ddof=1)),
            "mean_auroc": float(np.mean(metrics[name]["auroc"])),
            "sd_auroc": float(np.std(metrics[name]["auroc"], ddof=1)),
            "mean_brier": float(np.mean(metrics[name]["brier"])),
            "sd_brier": float(np.std(metrics[name]["brier"], ddof=1)),
            "mean_ll": float(np.mean(metrics[name]["ll"])),
            "sd_ll": float(np.std(metrics[name]["ll"], ddof=1)),
            "fold_auprc": metrics[name]["auprc"],
        }
    out["_summary"] = summary
    return out


def reliability_curve(y_true: np.ndarray, prob: np.ndarray, n_bins: int = 10):
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.digitize(prob, bins) - 1
    idx = np.clip(idx, 0, n_bins - 1)
    mean_pred = []
    frac_pos = []
    for b in range(n_bins):
        m = idx == b
        if not np.any(m):
            mean_pred.append(np.nan)
            frac_pos.append(np.nan)
            continue
        mean_pred.append(float(np.mean(prob[m])))
        frac_pos.append(float(np.mean(y_true[m])))
    return np.array(mean_pred), np.array(frac_pos)


def save_panel(path_stem: Path) -> None:
    path_stem.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(f"{path_stem}.png", dpi=SAVE_DPI, facecolor="white", edgecolor="none")
    plt.savefig(f"{path_stem}.pdf", facecolor="white", edgecolor="none")
    plt.close()


def figure1_panels(X: pd.DataFrame, y: np.ndarray, cv_out: dict, out_dir: Path) -> None:
    summary = cv_out["_summary"]
    keys = ["hgb", "rf", "lr"]

    # Panel: precision–recall (OOF)
    fig, ax = plt.subplots(figsize=(6.8, 5.6))
    for key, lab in [
        ("hgb", "HistGradientBoosting"),
        ("rf", "Random forest"),
        ("lr", "L2 logistic (balanced, liblinear)"),
    ]:
        p = cv_out[key]["oof"]
        prec, rec, _ = precision_recall_curve(y, p)
        ap = average_precision_score(y, p)
        ax.plot(rec, prec, color=COLORS[key], lw=2.8, label=f"{lab} (AP={ap:.3f})")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.legend(loc="upper right", framealpha=1.0)
    fig.tight_layout()
    save_panel(
        out_dir
        / "panel_precision_recall_curves_out_of_fold_predictions_stratified_K3"
    )

    # Panel: reliability / calibration — all three models (OOF, K=3)
    fig, ax = plt.subplots(figsize=(6.8, 5.6))
    ax.plot([0, 1], [0, 1], ls="--", color="#555555", lw=2.0, label="Perfect calibration")
    cal_labels = {
        "hgb": "HistGradientBoosting",
        "rf": "Random forest",
        "lr": "L2 logistic",
    }
    for key in keys:
        mp, fp = reliability_curve(y, cv_out[key]["oof"], n_bins=10)
        m = ~np.isnan(mp)
        ax.plot(
            mp[m],
            fp[m],
            "o-",
            color=COLORS[key],
            lw=2.4,
            markersize=7,
            markeredgecolor="#111111",
            markeredgewidth=0.6,
            label=cal_labels[key],
        )
    ax.set_xlabel("Mean predicted probability (bin)")
    ax.set_ylabel("Observed fraction positive (bin)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left", framealpha=1.0, fontsize=9)
    fig.tight_layout()
    save_panel(out_dir / "panel_reliability_calibration_three_models_stratified_K3")

    # Panel: metrics bar chart
    fig, ax = plt.subplots(figsize=(7.4, 5.8))
    labels = ["HistGrad.", "RF", "Logistic"]
    x = np.arange(4)
    w = 0.25
    mets = ["mean_auprc", "mean_auroc", "mean_brier", "mean_ll"]
    met_labels = ["AUPRC", "AUROC", "Brier", "Log-loss"]
    for i, k in enumerate(keys):
        vals = [summary[k][m] for m in mets]
        err = [
            summary[k]["sd_auprc"],
            summary[k]["sd_auroc"],
            summary[k]["sd_brier"],
            summary[k]["sd_ll"],
        ]
        ax.bar(
            x + (i - 1) * w,
            vals,
            width=w,
            yerr=err,
            capsize=3,
            label=labels[i],
            color=COLORS[k],
            edgecolor="#222222",
            linewidth=0.9,
            error_kw={"elinewidth": 1.4, "capthick": 1.4, "ecolor": "#111111"},
        )
    ax.set_xticks(x)
    ax.set_xticklabels(met_labels)
    ax.set_ylabel("Score (mean ± SD across folds)")
    ax.legend(loc="upper right", ncol=3, fontsize=9, framealpha=1.0)
    fig.tight_layout()
    save_panel(out_dir / "panel_crossvalidated_metrics_mean_SD_bars_stratified_K3")

    # Panel: fold-wise AUPRC
    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    for i, k in enumerate(keys):
        fa = summary[k]["fold_auprc"]
        xs = np.arange(1, N_SPLITS + 1) + i * 0.07
        ax.scatter(xs, fa, color=COLORS[k], s=85, zorder=3, edgecolors="#111111", linewidths=0.8)
        ax.plot(xs, fa, color=COLORS[k], lw=2.2)
    ax.set_xticks([1, 2, 3])
    ax.set_xlabel("Fold")
    ax.set_ylabel("AUPRC")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    lo = min(summary[k]["fold_auprc"][j] for k in keys for j in range(N_SPLITS))
    hi = max(summary[k]["fold_auprc"][j] for k in keys for j in range(N_SPLITS))
    pad = max(0.02, (hi - lo) * 0.12)
    ax.set_ylim(max(0, lo - pad), hi + pad)
    fig.tight_layout()
    save_panel(out_dir / "panel_foldwise_AUPRC_three_models_stratified_K3")


def _remove_obsolete_s2_panels(out_dir: Path) -> None:
    """Drop dual-strip and other files not used in Figure S2 (2×2, four singles)."""
    obsolete_stems = (
        "panel_partial_dependence_random_forest_average_Temperature_and_Year_two_features",
        "panel_partial_dependence_random_forest_average_Temperature",
        "panel_partial_dependence_random_forest_average_Vehicle_Damage_Cost",
    )
    obsolete_labeled = (
        "FigureS2c_PDP_temperature_and_year",
    )
    for stem in obsolete_stems:
        for ext in ("png", "pdf"):
            p = out_dir / f"{stem}.{ext}"
            if p.is_file():
                p.unlink()
    for name in obsolete_labeled:
        for ext in ("png", "pdf"):
            p = out_dir / f"{name}.{ext}"
            if p.is_file():
                p.unlink()


def figure2_panels(X: pd.DataFrame, y: np.ndarray, out_dir: Path) -> None:
    X_tr, _X_va, y_tr, _y_va = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )
    pre = make_preprocessor(sparse=False)
    pipe = Pipeline(
        [
            ("pre", pre),
            (
                "m",
                RandomForestClassifier(
                    n_estimators=120,
                    max_depth=16,
                    min_samples_leaf=4,
                    class_weight="balanced_subsample",
                    random_state=RANDOM_STATE,
                    n_jobs=1,
                ),
            ),
        ]
    )
    pipe.fit(X_tr, y_tr)
    rf = pipe.named_steps["m"]
    pre_fitted = pipe.named_steps["pre"]
    names = pre_fitted.get_feature_names_out()
    imp = rf.feature_importances_
    order = np.argsort(-imp)[:18]
    top_names = names[order]
    top_imp = imp[order]

    X_pd = X_tr.sample(min(3000, len(X_tr)), random_state=RANDOM_STATE)

    # Panel: importances
    fig, ax = plt.subplots(figsize=(7.8, 6.8))
    y_pos = np.arange(len(top_names))[::-1]
    ax.barh(
        y_pos,
        top_imp,
        color="#3d5a80",
        edgecolor="#111111",
        linewidth=0.85,
        height=0.72,
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(
        [n.replace("cat__", "").replace("num__", "")[:52] for n in top_names],
        fontsize=10,
    )
    ax.set_xlabel("Mean decrease in impurity (Gini)")
    ax.set_xlim(0, float(top_imp.max()) * 1.08)
    fig.tight_layout()
    save_panel(
        out_dir
        / "panel_random_forest_variable_importance_top18_Gini_diagnostic_80_20_stratified"
    )

    # Figure S2 (c): single PDP panels — same size as (b); no dual strip (2×2 Word layout)
    for fname, slug in (("User Age", "User_Age"), ("Year", "Year")):
        fig, ax = plt.subplots(figsize=(6.6, 5.2))
        disp = PartialDependenceDisplay.from_estimator(
            pipe,
            X_pd,
            features=[fname],
            ax=ax,
            kind="average",
            grid_resolution=20,
            line_kw={"color": COLORS["rf"], "lw": 3.0},
        )
        for a in np.ravel(disp.axes_):
            a.set_title("")
        ax.set_ylabel("")
        ax.set_xlabel(fname)
        ax.tick_params(axis="both", colors="#111111")
        for spine in ax.spines.values():
            spine.set_linewidth(1.1)
            spine.set_edgecolor("#222222")
        fig.tight_layout()
        save_panel(
            out_dir / f"panel_partial_dependence_random_forest_average_{slug}"
        )

    _remove_obsolete_s2_panels(out_dir)


def figure3_panels(df: pd.DataFrame, out_dir: Path) -> None:
    """Main-text Figure 2: recurrence burden (Q1-style panels)."""
    from scipy.stats import gaussian_kde

    y = df["Y"].values
    df = df.copy()
    gc_counts = df.groupby("Grade Crossing ID").size()
    harm = df[df["Y"] == 1]
    rho_hat = float((harm["Grade Crossing ID"].map(gc_counts) >= 2).sum() / max(len(harm), 1))

    # (A) Lorenz-type concentration with inequality shading
    fig, ax = new_panel()
    n_c = gc_counts.sort_values(ascending=False)
    sy = df.groupby("Grade Crossing ID")["Y"].sum()
    contrib = sy.reindex(n_c.index).fillna(0).values
    cum = np.cumsum(contrib) / max(y.sum(), 1)
    x_frac = np.arange(1, len(cum) + 1) / len(cum)
    ax.fill_between(x_frac, cum, x_frac, where=(cum >= x_frac), color=PALETTE["primary"], alpha=0.14)
    ax.fill_between(x_frac, 0, cum, color=PALETTE["primary"], alpha=0.07)
    ax.plot(x_frac, cum, color=PALETTE["primary"], lw=2.8, solid_capstyle="round", zorder=3)
    ax.plot([0, 1], [0, 1], ls=(0, (5, 4)), color=PALETTE["equality"], lw=1.8, zorder=2)
    ax.annotate(
        f"$\\hat{{\\rho}}$ = {rho_hat:.3f}",
        xy=(0.40, 0.70),
        xycoords="axes fraction",
        fontsize=12,
        color=PALETTE["primary"],
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor=PALETTE["grid"], alpha=0.95),
    )
    ax.set_xlabel("Share of crossings (ordered by incident count)")
    ax.set_ylabel("Cumulative share of harm events ($Y{=}1$)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    style_axes(ax, grid_axis="both")
    fig.tight_layout()
    save_figure(
        fig,
        out_dir
        / "panel_cumulative_share_injury_fatality_Y1_crossings_ordered_by_incident_count",
    )

    # (B) Inter-event gaps: log-scale KDE + rug + IQR markers
    gaps: list[float] = []
    for _cid, g in df.groupby("Grade Crossing ID"):
        if len(g) < 2:
            continue
        g = g.sort_values("Date")
        dts = pd.to_datetime(g["Date"], errors="coerce").diff().dt.days.dropna()
        gaps.extend(dts.astype(float).tolist())
    gaps = np.array(gaps)
    gaps = gaps[(gaps >= 1) & (gaps < 3650)]
    fig, ax = new_panel()
    if len(gaps) > 30:
        kde = gaussian_kde(gaps, bw_method=0.18)
        xs = np.linspace(gaps.min(), np.percentile(gaps, 99), 400)
        dens = kde(xs)
        ax.fill_between(xs, dens, color=PALETTE["tertiary"], alpha=0.35, linewidth=0)
        ax.plot(xs, dens, color=PALETTE["tertiary"], lw=2.4, zorder=3)
    med, q1, q3 = np.median(gaps), np.percentile(gaps, 25), np.percentile(gaps, 75)
    for val, ls in ((med, "-"), (q1, ":"), (q3, ":")):
        ax.axvline(val, color=PALETTE["secondary"], lw=1.35, ls=ls, alpha=0.8)
    sample = gaps if len(gaps) <= 800 else np.random.default_rng(42).choice(gaps, 800, replace=False)
    ax.plot(sample, np.zeros_like(sample), "|", color=PALETTE["ink"], alpha=0.15, markersize=3)
    ax.set_xlabel("Inter-event gap (days, log scale)")
    ax.set_ylabel("Density")
    ax.set_xscale("log")
    ax.set_xlim(max(1, gaps.min() * 0.9), np.percentile(gaps, 99.5) * 1.05)
    style_axes(ax, grid_axis="y")
    ax.text(
        0.98,
        0.94,
        f"Median = {med:.0f} d\nIQR = {q1:.0f}–{q3:.0f} d",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=PALETTE["grid"], alpha=0.92),
    )
    fig.tight_layout()
    save_figure(
        fig,
        out_dir
        / "panel_histogram_inter_event_gap_days_repeat_crossings_at_least_two_events",
    )

    # (C) Horizontal 100% composition by state
    states_order = ["CALIFORNIA", "GEORGIA", "MINNESOTA", "NEW JERSEY", "TEXAS", "WISCONSIN"]
    labels = ["California", "Georgia", "Minnesota", "New Jersey", "Texas", "Wisconsin"]
    rep_share: list[float] = []
    for st in states_order:
        m = (df["State Name"] == st) & (df["Y"] == 1)
        y1 = df.loc[m]
        if len(y1) == 0:
            rep_share.append(0.0)
            continue
        n_g = y1["Grade Crossing ID"].map(gc_counts)
        rep_share.append(float((n_g >= 2).mean()))
    sing_share = [1.0 - r for r in rep_share]
    y_pos = np.arange(len(labels))
    fig, ax = new_panel(figsize=(7.4, 5.6))
    ax.barh(
        y_pos,
        rep_share,
        height=0.62,
        color=PALETTE["repeat"],
        edgecolor="white",
        linewidth=0.8,
        label="Harm at repeat-active crossing",
    )
    ax.barh(
        y_pos,
        sing_share,
        left=rep_share,
        height=0.62,
        color=PALETTE["single"],
        edgecolor="white",
        linewidth=0.8,
        label="Harm at single-event crossing",
    )
    for i, r in enumerate(rep_share):
        if r >= 0.12:
            ax.text(
                r / 2,
                i,
                f"{r:.0%}",
                ha="center",
                va="center",
                fontsize=9,
                color="white",
                fontweight="bold",
            )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Share of $Y{=}1$ incidents")
    ax.invert_yaxis()
    ax.legend(loc="lower right", frameon=True, framealpha=0.98, fontsize=9)
    style_axes(ax, grid_axis="x")
    fig.tight_layout()
    save_figure(
        fig,
        out_dir / "panel_stacked_bars_Y1_share_repeat_crossing_vs_single_event_by_state",
    )

    # (D) Annual cohort volume: line + area (replaces bar chart)
    df["Year"] = pd.to_datetime(df["Date"], errors="coerce").dt.year
    vc = df.groupby("Year").size().sort_index()
    years = vc.index.astype(int).values
    counts = vc.values.astype(float)
    fig, ax = new_panel()
    ax.fill_between(years, counts, color=PALETTE["primary"], alpha=0.18)
    ax.plot(
        years,
        counts,
        color=PALETTE["primary"],
        lw=2.6,
        marker="o",
        markersize=6,
        markerfacecolor="white",
        markeredgewidth=1.8,
        markeredgecolor=PALETTE["primary"],
        zorder=3,
    )
    ax.set_xlabel("Calendar year")
    ax.set_ylabel("Incident count (six-state cohort)")
    ax.set_xlim(years.min() - 0.4, years.max() + 0.4)
    ax.set_ylim(0, counts.max() * 1.12)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
    style_axes(ax, grid_axis="y")
    fig.tight_layout()
    save_figure(fig, out_dir / "panel_annual_incident_counts_all_states")


def main() -> None:
    font_used = apply_publication_rc()
    print(f"Matplotlib font: {font_used}", flush=True)
    print("Loading data…", flush=True)
    df = load_frame()
    n_expected = expected_cohort_n()
    assert len(df) == n_expected, f"Expected N={n_expected} from cohort manifest, got {len(df)}"
    X, y = make_Xy(df)
    models = build_models()
    print("Cross-validation (3-fold)…", flush=True)
    cv_out = cv_oof_and_fold_metrics(X, y, models)

    d1 = FIG_ROOT / DIR_S1_LEGACY_CV
    d2 = FIG_ROOT / DIR_S2_LEGACY_RF
    d3 = FIG_ROOT / "Figure3_recurrence_burden"

    print("Figure 1 panels…", flush=True)
    figure1_panels(X, y, cv_out, d1)
    print("Figure 2 panels…", flush=True)
    figure2_panels(X, y, d2)
    print("Figure 3 panels (main-text Figure 2)…", flush=True)
    figure3_panels(df, d3)
    n_f2 = label_main_figure_2_panels(FIG_ROOT)
    print(f"Main Figure 2 labeled copies: {n_f2} files", flush=True)

    lines = [
        "# CV summary (auto from build_manuscript_figures.py)",
        f"# Figure panels directory: {FIG_ROOT}",
        "",
    ]
    for k in ["hgb", "rf", "lr"]:
        s = cv_out["_summary"][k]
        lines.append(
            f"{k}: AUPRC {s['mean_auprc']:.4f}±{s['sd_auprc']:.4f} | "
            f"AUROC {s['mean_auroc']:.4f}±{s['sd_auroc']:.4f} | "
            f"Brier {s['mean_brier']:.4f}±{s['sd_brier']:.4f} | "
            f"logloss {s['mean_ll']:.4f}±{s['sd_ll']:.4f}"
        )
    (FIG_ROOT / "figure_cv_metrics.txt").write_text("\n".join(lines), encoding="utf-8")
    write_cv_metrics_json(cv_out["_summary"])

    manifest_lines = [
        "# Panel files for Word/slides — see FIGURE_S1_WORD_LAYOUT.md and FIGURE_S2_WORD_LAYOUT.md",
        f"# Base directory: {FIG_ROOT}",
        "",
    ]
    order_f1_labeled = [
        ("a", "panel_precision_recall_curves_out_of_fold_predictions_stratified_K3"),
        ("b", "panel_reliability_calibration_three_models_stratified_K3"),
        ("c", "panel_crossvalidated_metrics_mean_SD_bars_stratified_K3"),
        ("d", "panel_foldwise_AUPRC_three_models_stratified_K3"),
    ]
    # Figure S2: 2×2 layout — (d) treeshap_mean_abs_bar from run_treeshap_analysis.py
    order_f2_labeled = [
        ("a", "panel_random_forest_variable_importance_top18_Gini_diagnostic_80_20_stratified"),
        ("b", "panel_partial_dependence_random_forest_average_User_Age"),
        ("c", "panel_partial_dependence_random_forest_average_Year"),
        ("d", "treeshap_mean_abs_bar"),
    ]
    order_f3 = [
        "panel_cumulative_share_injury_fatality_Y1_crossings_ordered_by_incident_count",
        "panel_histogram_inter_event_gap_days_repeat_crossings_at_least_two_events",
        "panel_stacked_bars_Y1_share_repeat_crossing_vs_single_event_by_state",
        "panel_annual_incident_counts_all_states",
    ]
    sync_counts = sync_supplementary_aliases(FIG_ROOT)
    print(
        f"Supplementary aliases: {DIR_S1_DIAGNOSTIC_CV} ({sync_counts[DIR_S1_DIAGNOSTIC_CV]} files), "
        f"{DIR_S2_RF_STRUCTURE} ({sync_counts[DIR_S2_RF_STRUCTURE]} files)",
        flush=True,
    )

    def _append_manifest_labeled(
        folder_name: str, labeled: list[tuple[str, str]], note: str = ""
    ) -> None:
        sub = FIG_ROOT / folder_name
        manifest_lines.append(f"## {folder_name}")
        if note:
            manifest_lines.append(f"# {note}")
        for letter, stem in labeled:
            if (sub / f"{stem}.png").is_file() or (sub / f"{stem}.pdf").is_file():
                manifest_lines.append(f"  ({letter}) {stem}")
        manifest_lines.append("")

    def _append_manifest_section(folder_name: str, stems: list[str], note: str = "") -> None:
        sub = FIG_ROOT / folder_name
        manifest_lines.append(f"## {folder_name}")
        if note:
            manifest_lines.append(f"# {note}")
        for stem in stems:
            if (sub / f"{stem}.png").is_file() or (sub / f"{stem}.pdf").is_file():
                manifest_lines.append(f"  {stem}")
        manifest_lines.append("")

    _append_manifest_labeled(
        DIR_S1_DIAGNOSTIC_CV,
        order_f1_labeled,
        "Supplementary Figure S1 — 2×2 Word layout (FIGURE_S1_WORD_LAYOUT.md)",
    )
    _append_manifest_labeled(
        DIR_S1_LEGACY_CV,
        order_f1_labeled,
        f"Legacy alias — same panels as {DIR_S1_DIAGNOSTIC_CV}",
    )
    _append_manifest_labeled(
        DIR_S2_RF_STRUCTURE,
        order_f2_labeled,
        "Supplementary Figure S2 — 2×2 Word layout (FIGURE_S2_WORD_LAYOUT.md)",
    )
    _append_manifest_labeled(
        DIR_S2_LEGACY_RF,
        order_f2_labeled,
        f"Legacy alias — same panels as {DIR_S2_RF_STRUCTURE}",
    )
    order_f3_labeled = [(letter, stem) for letter, stem, _short in MAIN_FIGURE_2_PANELS]
    _append_manifest_labeled(
        DIR_MAIN_RECURRENCE,
        order_f3_labeled,
        "Main-text Figure 2 — 2×2 (FIGURE_2_WORD_LAYOUT.md)",
    )
    (FIG_ROOT / "PANEL_MANIFEST.txt").write_text("\n".join(manifest_lines), encoding="utf-8")

    print("Wrote panels to", FIG_ROOT)
    print("\n".join(lines))


if __name__ == "__main__":
    main()

