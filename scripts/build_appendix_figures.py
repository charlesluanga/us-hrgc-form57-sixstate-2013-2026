"""
Appendix figures: permutation importance (RQ2) and visibility-stratified harm rates.
Outputs: outputs/figures/Appendix_interpretability/
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

warnings.filterwarnings("ignore")

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from build_manuscript_figures import (  # noqa: E402
    CAT_COLS,
    CSV_PATH,
    NUM_COLS,
    RANDOM_STATE,
    SAVE_DPI,
    apply_publication_rc,
    load_frame,
    make_Xy,
    save_panel,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "manuscript" / "figures" / "Appendix_interpretability"
N_PERM = 15


def rf_pipeline() -> Pipeline:
    cat_pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="constant", fill_value="missing")),
            ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    pre = ColumnTransformer(
        [("cat", cat_pipe, CAT_COLS), ("num", SimpleImputer(strategy="median"), NUM_COLS)]
    )
    return Pipeline(
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


def simplify_feature_name(name: str) -> str:
    name = str(name)
    if name.startswith("num__"):
        return name.replace("num__", "")
    if name.startswith("cat__"):
        rest = name.replace("cat__", "")
        if "_" in rest:
            base, val = rest.split("_", 1)
            return f"{base}: {val}"
        return rest
    return name


def panel_global_permutation(X: pd.DataFrame, y: np.ndarray, out_dir: Path) -> None:
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )
    pipe = rf_pipeline()
    pipe.fit(X_tr, y_tr)
    perm = permutation_importance(
        pipe,
        X_te,
        y_te,
        n_repeats=N_PERM,
        random_state=RANDOM_STATE,
        n_jobs=1,
        scoring="average_precision",
    )
    names = [simplify_feature_name(n) for n in pipe.named_steps["pre"].get_feature_names_out()]
    order = np.argsort(perm.importances_mean)[::-1][:12]
    order = order[::-1]

    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    y_pos = np.arange(len(order))
    means = perm.importances_mean[order]
    stds = perm.importances_std[order]
    labels = [names[i] for i in order]
    ax.barh(
        y_pos,
        means,
        xerr=stds,
        color="#4a6fa5",
        edgecolor="#111111",
        linewidth=0.8,
        capsize=3,
        error_kw={"elinewidth": 1.2, "capthick": 1.2, "ecolor": "#111111"},
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Permutation importance (AUPRC decrease)")
    ax.axvline(0, color="#555555", lw=0.8)
    fig.tight_layout()
    save_panel(out_dir / "panel_appendix_permutation_importance_top12_global_RF")


def panel_importance_by_state(X: pd.DataFrame, y: np.ndarray, df: pd.DataFrame, out_dir: Path) -> None:
    """Top feature: mean |permutation importance| evaluated on each state's hold-out rows."""
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )
    pipe = rf_pipeline()
    pipe.fit(X_tr, y_tr)
    perm_full = permutation_importance(
        pipe, X_te, y_te, n_repeats=8, random_state=RANDOM_STATE, n_jobs=1, scoring="average_precision"
    )
    names = [simplify_feature_name(n) for n in pipe.named_steps["pre"].get_feature_names_out()]
    top_idx = np.argsort(perm_full.importances_mean)[::-1][:8]
    top_names = [names[i] for i in top_idx]

    states = sorted(df["State Name"].dropna().unique())
    mat = np.zeros((len(states), len(top_idx)))
    state_on_te = df.loc[X_te.index, "State Name"]
    for si, st in enumerate(states):
        mask = (state_on_te == st).values
        if mask.sum() < 40:
            mat[si, :] = np.nan
            continue
        p = permutation_importance(
            pipe,
            X_te.iloc[mask],
            y_te[mask],
            n_repeats=5,
            random_state=RANDOM_STATE,
            n_jobs=1,
            scoring="average_precision",
        )
        mat[si, :] = p.importances_mean[top_idx]

    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    im = ax.imshow(mat, aspect="auto", cmap="Blues", vmin=0)
    ax.set_xticks(range(len(top_names)))
    ax.set_xticklabels(top_names, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(states)))
    ax.set_yticklabels([s.title() for s in states], fontsize=9)
    ax.set_xlabel("Top global features (permutation importance on state hold-out rows)")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    save_panel(out_dir / "panel_appendix_permutation_importance_heatmap_by_state")


def panel_visibility_harm_by_state(df: pd.DataFrame, out_dir: Path) -> None:
    states = sorted(df["State Name"].dropna().unique())
    dark_rates, day_rates = [], []
    for st in states:
        g = df[df["State Name"] == st]
        dark_rates.append(g.loc[g["Visibility"] == "Dark", "Y"].mean() if (g["Visibility"] == "Dark").any() else np.nan)
        day_rates.append(g.loc[g["Visibility"] == "Day", "Y"].mean() if (g["Visibility"] == "Day").any() else np.nan)

    x = np.arange(len(states))
    w = 0.36
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.bar(x - w / 2, dark_rates, w, label="Dark", color="#2c3e50", edgecolor="#111111", linewidth=0.7)
    ax.bar(x + w / 2, day_rates, w, label="Day", color="#f39c12", edgecolor="#111111", linewidth=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels([s.title() for s in states], rotation=25, ha="right")
    ax.set_ylabel("Harm prevalence (Y = 1)")
    ax.set_ylim(0, 0.65)
    ax.legend(loc="upper right")
    fig.tight_layout()
    save_panel(out_dir / "panel_appendix_harm_prevalence_dark_vs_day_by_state")


def main() -> None:
    apply_publication_rc()
    df = load_frame()
    X, y = make_Xy(df)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Appendix: global permutation…", flush=True)
    panel_global_permutation(X, y, OUT_DIR)
    print("Appendix: state heatmap…", flush=True)
    panel_importance_by_state(X, y, df, OUT_DIR)
    print("Appendix: visibility harm by state…", flush=True)
    panel_visibility_harm_by_state(df, OUT_DIR)
    print("Wrote", OUT_DIR)


if __name__ == "__main__":
    main()

