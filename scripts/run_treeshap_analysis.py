"""TreeSHAP for locked histgradient harm model; merge into revision_results.json."""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

warnings.filterwarnings("ignore")

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from figure_paths import DIR_S2_LEGACY_RF, DIR_S2_RF_STRUCTURE, sync_supplementary_aliases
from figure_style import SAVE_DPI, apply_publication_rc
from run_revision_analyses import (  # noqa: E402
    CAT,
    NUM_NO_DAMAGE,
    OUT,
    RANDOM_STATE,
    hgb_pipeline,
    load_df,
)

ROOT = Path(__file__).resolve().parents[1]
FIG_ROOT = ROOT / "outputs" / "figures"
FIG_DIR = FIG_ROOT / DIR_S2_LEGACY_RF
FIG_DIR.mkdir(parents=True, exist_ok=True)

MAX_BACKGROUND = 400
MAX_EXPLAIN = 600


def feature_names_from_preprocessor(pre, n_features: int) -> list[str]:
    try:
        names = pre.get_feature_names_out()
        return [str(x) for x in names]
    except Exception:
        return [f"f{i}" for i in range(n_features)]


def main() -> None:
    df = load_df()
    cats = CAT
    nums = NUM_NO_DAMAGE
    X = df[cats + nums]
    y = df["Y"].values

    pipe = hgb_pipeline(cats, nums)
    # Temporal holdout: train <= 2023, explain 2024-2025
    tr = df[df["Year"] <= 2023]
    te = df[df["Year"] >= 2024]
    pipe.fit(tr[cats + nums], tr["Y"])

    pre = pipe.named_steps["pre"]
    clf = pipe.named_steps["m"]
    X_bg = pre.transform(tr[cats + nums].sample(min(MAX_BACKGROUND, len(tr)), random_state=RANDOM_STATE))
    if hasattr(X_bg, "toarray"):
        X_bg = X_bg.toarray()
    X_ex = pre.transform(te[cats + nums].sample(min(MAX_EXPLAIN, len(te)), random_state=RANDOM_STATE + 1))
    if hasattr(X_ex, "toarray"):
        X_ex = X_ex.toarray()

    explainer = shap.TreeExplainer(clf)
    shap_values = explainer.shap_values(X_ex)
    if isinstance(shap_values, list):
        shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]

    names = feature_names_from_preprocessor(pre, X_ex.shape[1])
    mean_abs = np.abs(shap_values).mean(axis=0)
    order = np.argsort(mean_abs)[::-1]
    top = [
        {"feature": names[i], "mean_abs_shap": float(mean_abs[i])}
        for i in order[:20]
    ]

    font_used = apply_publication_rc()
    k = min(15, len(top))
    feats = [top[i]["feature"] for i in range(k)][::-1]
    vals = [top[i]["mean_abs_shap"] for i in range(k)][::-1]
    fig, ax = plt.subplots(figsize=(6.6, 5.2))
    ax.barh(range(k), vals, color="#2c5f8a", edgecolor="#111111", linewidth=0.85, height=0.72)
    ax.set_yticks(range(k))
    ax.set_yticklabels([f.replace("cat__", "").replace("num__", "") for f in feats])
    ax.set_xlabel("Mean |SHAP| (held-out 2024–2025 sample)")
    for spine in ax.spines.values():
        spine.set_linewidth(1.1)
        spine.set_edgecolor("#222222")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(
            FIG_DIR / f"treeshap_mean_abs_bar.{ext}",
            dpi=SAVE_DPI if ext == "png" else None,
            facecolor="white",
            edgecolor="none",
        )
    plt.close(fig)

    out = {
        "model": "HistGradientBoostingClassifier",
        "feature_set": "core_excluding_damage_cost",
        "train_years": "<=2023",
        "explain_years": "2024-2025",
        "n_background": int(X_bg.shape[0]),
        "n_explained": int(X_ex.shape[0]),
        "top_features": top,
        "note": "TreeSHAP on preprocessed design matrix; associational ranking only.",
    }

    base = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
    base["treeshap_hgb"] = out
    OUT.write_text(json.dumps(base, indent=2), encoding="utf-8")
    sync_counts = sync_supplementary_aliases(FIG_ROOT)
    print(f"Matplotlib font: {font_used}", flush=True)
    print(f"TreeSHAP top feature: {top[0]['feature']}", flush=True)
    print(f"Wrote figure -> {FIG_DIR}", flush=True)
    print(
        f"Mirrored TreeSHAP -> {FIG_ROOT / DIR_S2_RF_STRUCTURE} "
        f"({sync_counts[DIR_S2_RF_STRUCTURE]} files)",
        flush=True,
    )
    print(f"Merged -> {OUT}", flush=True)


if __name__ == "__main__":
    main()

