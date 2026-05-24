"""
Revision analyses addressing first-round reviewer comments.
Outputs: outputs/revision_results.json
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
from scipy import stats
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, log_loss
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "all_states.csv"
FRA = ROOT / "Highway-Rail_Grade_Crossing_Incident_Data__Form_57_.csv"
OUT = ROOT / "manuscript" / "exports" / "revision_results.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
N_BOOT = 2000
N_BOOT_QUICK = 200  # fallback label only
CV = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)

CAT = [
    "State Name",
    "Visibility",
    "Weather Condition",
    "Roadway Condition",
    "Track Type",
    "Highway User",
    "Highway User Position",
]
NUM = ["Year", "Temperature", "Vehicle Damage Cost", "User Age"]
NUM_NO_DAMAGE = ["Year", "Temperature", "User Age"]


def load_df() -> pd.DataFrame:
    df = pd.read_csv(CSV, low_memory=False)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Year"] = df["Date"].dt.year
    k = pd.to_numeric(df["Total Killed Form 57"], errors="coerce").fillna(0)
    j = pd.to_numeric(df["Total Injured Form 57"], errors="coerce").fillna(0)
    df["Y"] = ((k >= 1) | (j >= 1)).astype(int)
    df["Y_fat"] = (k >= 1).astype(int)
    df["Y_inj_only"] = ((j >= 1) & (k < 1)).astype(int)
    df["dark"] = (df["Visibility"] == "Dark").astype(int)
    df["low_vis"] = df["Visibility"].isin(["Dark", "Dusk", "Dawn"]).astype(int)
    return df


def make_preprocessor(cats: list[str], nums: list[str], sparse: bool = False) -> ColumnTransformer:
    cat_pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="constant", fill_value="missing")),
            ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=sparse)),
        ]
    )
    return ColumnTransformer(
        [("cat", cat_pipe, cats), ("num", SimpleImputer(strategy="median"), nums)]
    )


def hgb_pipeline(cats: list[str], nums: list[str]) -> Pipeline:
    return Pipeline(
        [
            ("pre", make_preprocessor(cats, nums)),
            (
                "m",
                HistGradientBoostingClassifier(
                    max_iter=80,
                    learning_rate=0.12,
                    max_depth=8,
                    min_samples_leaf=20,
                    l2_regularization=0.15,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def cv_metrics(df: pd.DataFrame, y_col: str, cats: list[str], nums: list[str]) -> dict:
    X = df[cats + nums]
    y = df[y_col].values
    pipe = hgb_pipeline(cats, nums)
    auprcs, lls = [], []
    for tr, te in CV.split(X, y):
        m = clone(pipe)
        m.fit(X.iloc[tr], y[tr])
        p = m.predict_proba(X.iloc[te])[:, 1]
        auprcs.append(average_precision_score(y[te], p))
        lls.append(log_loss(y[te], p, labels=[0, 1]))
    return {
        "mean_auprc": float(np.mean(auprcs)),
        "sd_auprc": float(np.std(auprcs)),
        "mean_log_loss": float(np.mean(lls)),
        "sd_log_loss": float(np.std(lls)),
    }


def pareto_top_decile_harm_share(df: pd.DataFrame, y_col: str = "Y") -> dict:
    gc = df.groupby("Grade Crossing ID").agg(incidents=(y_col, "count"), harm=(y_col, "sum"))
    gc = gc.sort_values("incidents", ascending=False)
    n_top = max(1, int(np.ceil(0.1 * len(gc))))
    top = gc.head(n_top)
    total_harm = float(df[y_col].sum())
    return {
        "top_decile_crossings": int(n_top),
        "share_harm_top_decile": float(top["harm"].sum() / total_harm) if total_harm else None,
    }


def state_weighted_harm_rate(df: pd.DataFrame, y_col: str = "Y") -> dict:
    """Harm rate reweighted to national incident shares among the six study states."""
    study = {"CALIFORNIA", "GEORGIA", "MINNESOTA", "NEW JERSEY", "TEXAS", "WISCONSIN"}
    usecols = ["State Name", "Date", "Total Killed Form 57", "Total Injured Form 57"]
    raw = pd.read_csv(FRA, usecols=usecols, low_memory=False)
    raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
    raw = raw[(raw["Date"] >= "2013-01-01") & (raw["Date"] <= "2026-12-31")]
    raw["State Name"] = raw["State Name"].astype(str).str.strip().str.upper()
    nat = raw[raw["State Name"].isin(study)]
    w = nat["State Name"].value_counts(normalize=True)
    rates = df.groupby("State Name")[y_col].mean()
    aligned = rates.reindex(w.index).dropna()
    w = w.reindex(aligned.index)
    w = w / w.sum()
    return {
        "unweighted_harm_rate": float(df[y_col].mean()),
        "national_share_weighted_harm_rate": float((aligned * w).sum()),
        "state_weights": {k: float(v) for k, v in w.items()},
    }


def winsor_damage_cost(df: pd.DataFrame, q: float = 0.99) -> pd.DataFrame:
    out = df.copy()
    dc = pd.to_numeric(out["Vehicle Damage Cost"], errors="coerce")
    cap = dc.quantile(q)
    out["Vehicle Damage Cost"] = dc.clip(upper=cap)
    return out, float(cap)


def model_auprc_fold_bootstrap(df: pd.DataFrame, y_col: str = "Y") -> dict:
    """Bootstrap mean fold AUPRC difference (HGB minus RF) on stratified 3-fold CV."""
    X = df[CAT + NUM]
    y = df[y_col].values
    hgb_pipe = hgb_pipeline(CAT, NUM)
    rf_pipe = Pipeline(
        [
            ("pre", make_preprocessor(CAT, NUM)),
            (
                "m",
                RandomForestClassifier(
                    n_estimators=120,
                    max_depth=14,
                    min_samples_leaf=6,
                    class_weight="balanced_subsample",
                    random_state=RANDOM_STATE,
                    n_jobs=1,
                ),
            ),
        ]
    )
    diffs = []
    for tr, te in CV.split(X, y):
        mh = clone(hgb_pipe)
        mr = clone(rf_pipe)
        mh.fit(X.iloc[tr], y[tr])
        mr.fit(X.iloc[tr], y[tr])
        ph = mh.predict_proba(X.iloc[te])[:, 1]
        pr = mr.predict_proba(X.iloc[te])[:, 1]
        diffs.append(average_precision_score(y[te], ph) - average_precision_score(y[te], pr))
    rng = np.random.default_rng(RANDOM_STATE)
    boot = []
    arr = np.array(diffs)
    for _ in range(N_BOOT):
        samp = rng.choice(arr, size=len(arr), replace=True)
        boot.append(float(samp.mean()))
    return {
        "fold_auprc_diff_hgb_minus_rf": [float(x) for x in diffs],
        "mean_diff": float(np.mean(diffs)),
        "boot_ci95_low": float(np.percentile(boot, 2.5)),
        "boot_ci95_high": float(np.percentile(boot, 97.5)),
    }


def h1_logit_or(df: pd.DataFrame, y_col: str = "Y") -> tuple[float, float]:
    d = df.copy()
    d["Yv"] = d[y_col]
    formula = "Yv ~ dark + Year + C(Q('State Name'), Treatment(reference='CALIFORNIA'))"
    yv, Xv = patsy.dmatrices(formula, d, return_type="dataframe")
    fit = sm.Logit(yv, Xv).fit(disp=0)
    b = float(fit.params["dark"])
    return b, float(np.exp(b))


def bootstrap_h1_or(df: pd.DataFrame, y_col: str = "Y") -> dict:
    states = df["State Name"].unique()
    rng = np.random.default_rng(RANDOM_STATE)
    ors = []
    for b in range(N_BOOT):
        samp_states = rng.choice(states, size=len(states), replace=True)
        parts = [df.loc[df["State Name"] == s] for s in samp_states]
        bdf = pd.concat(parts, ignore_index=True)
        try:
            _, orv = h1_logit_or(bdf, y_col)
            ors.append(orv)
        except Exception:
            continue
        if (b + 1) % 50 == 0:
            print(f"  bootstrap {b + 1}/{N_BOOT}", flush=True)
    ors = np.array(ors)
    return {
        "point_or": float(h1_logit_or(df, y_col)[1]),
        "boot_median_or": float(np.median(ors)),
        "ci95_low": float(np.percentile(ors, 2.5)),
        "ci95_high": float(np.percentile(ors, 97.5)),
        "n_boot_success": int(len(ors)),
    }


def burden_rho(df: pd.DataFrame, y_col: str, min_count: int) -> float:
    y = df[y_col].values
    gid = df["Grade Crossing ID"]
    counts = gid.map(gid.value_counts())
    mask = counts >= min_count
    num = y[mask].sum()
    den = y.sum()
    return float(num / den) if den else float("nan")


def _precompute_cluster_row_indices(inv: np.ndarray, n_clusters: int) -> list[np.ndarray]:
    return [np.flatnonzero(inv == g) for g in range(n_clusters)]


def _cluster_bootstrap_indices(
    clusters: list[np.ndarray], n_clusters: int, rng: np.random.Generator
) -> np.ndarray:
    """Row indices for one cluster bootstrap replicate (crossing = cluster)."""
    draws = rng.integers(0, n_clusters, size=n_clusters)
    return np.concatenate([clusters[g] for g in draws])


def bootstrap_rho_crossing(df: pd.DataFrame, y_col: str = "Y", min_count: int = 2) -> dict:
    """Cluster bootstrap at crossing ID (resample crossings with replacement)."""
    y = df[y_col].values.astype(float)
    inv, uniques = pd.factorize(df["Grade Crossing ID"])
    inv = inv.astype(np.int64)
    n_g = len(uniques)
    clusters = _precompute_cluster_row_indices(inv, n_g)
    rng = np.random.default_rng(RANDOM_STATE)
    rhos = []
    for b in range(N_BOOT):
        idx = _cluster_bootstrap_indices(clusters, n_g, rng)
        y_b = y[idx]
        gid_b = inv[idx]
        counts_b = np.bincount(gid_b, minlength=n_g)
        repeat = counts_b[gid_b] >= min_count
        den = y_b.sum()
        num = y_b[repeat].sum() if den else 0.0
        rhos.append(float(num / den) if den else float("nan"))
        if (b + 1) % 500 == 0:
            print(f"  rho bootstrap {b + 1}/{N_BOOT}", flush=True)
    rhos = np.array(rhos)
    pt = burden_rho(df, y_col, min_count)
    return {
        "point": pt,
        "ci95_low": float(np.percentile(rhos, 2.5)),
        "ci95_high": float(np.percentile(rhos, 97.5)),
        "min_crossing_incidents": min_count,
        "bootstrap_unit": "crossing_id",
    }


def bootstrap_gini_crossing(df: pd.DataFrame) -> dict:
    inv, uniques = pd.factorize(df["Grade Crossing ID"])
    inv = inv.astype(np.int64)
    n_g = len(uniques)
    counts = np.bincount(inv)
    pt = gini_coefficient(counts)
    clusters = _precompute_cluster_row_indices(inv, n_g)
    rng = np.random.default_rng(RANDOM_STATE + 1)
    ginis = []
    for b in range(N_BOOT):
        idx = _cluster_bootstrap_indices(clusters, n_g, rng)
        ginis.append(gini_coefficient(np.bincount(inv[idx])))
        if (b + 1) % 500 == 0:
            print(f"  gini bootstrap {b + 1}/{N_BOOT}", flush=True)
    ginis = np.array(ginis)
    return {
        "point": float(pt),
        "ci95_low": float(np.percentile(ginis, 2.5)),
        "ci95_high": float(np.percentile(ginis, 97.5)),
        "bootstrap_unit": "crossing_id",
    }


def wild_cluster_bootstrap_h1(df: pd.DataFrame, y_col: str = "Y", B: int | None = None) -> dict:
    """Rademacher wild cluster bootstrap (G=6 states) for dark coefficient."""
    B = B or N_BOOT
    d = df.copy()
    d["Yv"] = d[y_col]
    formula = "Yv ~ dark + Year + C(Q('State Name'), Treatment(reference='CALIFORNIA'))"
    yv, Xv = patsy.dmatrices(formula, d, return_type="dataframe")
    fit = sm.Logit(yv, Xv).fit(disp=0)
    clusters = sorted(d.loc[yv.index, "State Name"].unique())
    state_idx = d.loc[yv.index, "State Name"].values
    rng = np.random.default_rng(RANDOM_STATE + 2)
    boot_ors = []
    for b in range(B):
        w = rng.choice([-1.0, 1.0], size=len(clusters))
        wmap = dict(zip(clusters, w))
        freq = np.array([abs(wmap[s]) for s in state_idx])
        try:
            fit_b = sm.GLM(
                yv, Xv, family=sm.families.Binomial(), freq_weights=freq
            ).fit(disp=0)
            boot_ors.append(float(np.exp(fit_b.params["dark"])))
        except Exception:
            continue
        if (b + 1) % 500 == 0:
            print(f"  wild cluster {b + 1}/{B}", flush=True)
    boot_ors = np.array(boot_ors)
    fit_hc3 = sm.Logit(yv, Xv).fit(disp=0, cov_type="HC3")
    return {
        "point_or": float(np.exp(fit.params["dark"])),
        "wild_cluster_ci95_low": float(np.percentile(boot_ors, 2.5)),
        "wild_cluster_ci95_high": float(np.percentile(boot_ors, 97.5)),
        "n_wild_success": int(len(boot_ors)),
        "hc3_or": float(np.exp(fit_hc3.params["dark"])),
        "hc3_ci95_low": float(np.exp(fit_hc3.conf_int().loc["dark", 0])),
        "hc3_ci95_high": float(np.exp(fit_hc3.conf_int().loc["dark", 1])),
        "n_clusters": len(clusters),
    }


def null_rho_permutation(df: pd.DataFrame, y_col: str = "Y", min_count: int = 2, n_sim: int = 5000) -> dict:
    """Permute harm labels across incidents; benchmark observed rho."""
    y = df[y_col].values.astype(float)
    ng = df.groupby("Grade Crossing ID").size()
    repeat_mask = (df["Grade Crossing ID"].map(ng) >= min_count).values
    den = float(y.sum())
    rng = np.random.default_rng(RANDOM_STATE + 3)
    rhos = np.empty(n_sim)
    for i in range(n_sim):
        y_perm = rng.permutation(y)
        rhos[i] = float(y_perm[repeat_mask].sum() / den) if den else float("nan")
    obs = burden_rho(df, y_col, min_count)
    return {
        "observed_rho": float(obs),
        "null_mean": float(rhos.mean()),
        "null_sd": float(rhos.std()),
        "null_p95": float(np.percentile(rhos, 95)),
        "null_p99": float(np.percentile(rhos, 99)),
        "empirical_p_gt_obs": float((rhos >= obs).mean()),
        "n_sim": n_sim,
    }


def rolling_origin_unseen_crossings(df: pd.DataFrame) -> dict:
    """Train on years < t; test only crossings with no prior incidents in train window."""
    years = sorted(df["Year"].dropna().unique())
    pipe = hgb_pipeline(CAT, NUM)
    folds = []
    for test_year in years:
        if test_year < 2015:
            continue
        tr = df[df["Year"] < test_year]
        te = df[df["Year"] == test_year]
        seen = set(tr["Grade Crossing ID"])
        te_new = te[~te["Grade Crossing ID"].isin(seen)]
        if len(te_new) < 25 or tr["Y"].nunique() < 2:
            continue
        m = clone(pipe)
        m.fit(tr[CAT + NUM], tr["Y"])
        p = m.predict_proba(te_new[CAT + NUM])[:, 1]
        folds.append(
            {
                "test_year": int(test_year),
                "n_train": int(len(tr)),
                "n_test_unseen_crossings": int(len(te_new)),
                "n_test_all_year": int(len(te)),
                "auprc": float(average_precision_score(te_new["Y"], p)),
                "log_loss": float(log_loss(te_new["Y"], p, labels=[0, 1])),
            }
        )
    return {
        "folds": folds,
        "mean_auprc": float(np.mean([x["auprc"] for x in folds])) if folds else None,
        "mean_log_loss": float(np.mean([x["log_loss"] for x in folds])) if folds else None,
        "note": "Test rows restricted to crossings with zero incidents before test year.",
    }


def missingness_diagnostics(df: pd.DataFrame) -> dict:
    cols = ["User Age", "Vehicle Damage Cost", "Estimated Vehicle Speed", "Visibility"]
    out = {}
    for c in cols:
        if c not in df.columns:
            continue
        miss = df[c].isna() | (df[c] == "") if df[c].dtype == object else df[c].isna()
        if c == "User Age":
            miss = miss | (pd.to_numeric(df[c], errors="coerce") == 0)
        out[c] = {
            "pct_missing": float(miss.mean()),
            "n_missing": int(miss.sum()),
            "harm_rate_if_missing": float(df.loc[miss, "Y"].mean()) if miss.any() else None,
            "harm_rate_if_observed": float(df.loc[~miss, "Y"].mean()) if (~miss).any() else None,
        }
    # User Age indicator sensitivity
    age_miss = out.get("User Age", {}).get("pct_missing", 0) > 0
    if age_miss:
        m = df["User Age"].isna() | (pd.to_numeric(df["User Age"], errors="coerce") == 0)
        d = df.copy()
        d["age_missing"] = m.astype(int)
        try:
            yv, Xv = patsy.dmatrices(
                "Y ~ age_missing + dark + Year + C(Q('State Name'))", d, return_type="dataframe"
            )
            fit = sm.Logit(yv, Xv).fit(disp=0)
            out["age_missing_indicator"] = {
                "or": float(np.exp(fit.params["age_missing"])),
                "pvalue": float(fit.pvalues["age_missing"]),
            }
        except Exception:
            pass
    return out


def california_fatality_audit(df: pd.DataFrame) -> dict:
    ca = df[df["State Name"].str.upper() == "CALIFORNIA"].copy()
    k = pd.to_numeric(ca["Total Killed Form 57"], errors="coerce").fillna(0)
    j = pd.to_numeric(ca["Total Injured Form 57"], errors="coerce").fillna(0)
    harm = ca["Y"] == 1
    fat = k >= 1
    dup_gid = int(ca["Grade Crossing ID"].duplicated().sum())
    n_rows_dup_gid = int(ca[ca["Grade Crossing ID"].duplicated(keep=False)].shape[0])
    fat_among_harm = float(fat[harm].mean()) if harm.any() else None
    inj_only_harm = float(((j >= 1) & (k < 1))[harm].mean()) if harm.any() else None
    return {
        "n_incidents": int(len(ca)),
        "fatality_rate_all": float(fat.mean()),
        "harm_rate": float(harm.mean()),
        "fatality_share_among_harm_rows": fat_among_harm,
        "injury_only_share_among_harm_rows": inj_only_harm,
        "duplicate_crossing_id_rows": n_rows_dup_gid,
        "unique_crossings": int(ca["Grade Crossing ID"].nunique()),
        "max_killed_single_incident": float(k.max()),
        "incidents_killed_ge2": int((k >= 2).sum()),
        "note": "Duplicates expected (repeat incidents); audit checks coding extremes.",
    }


def leakage_audit_rows() -> list[dict]:
    return [
        {
            "variable": "Vehicle Damage Cost",
            "timing": "Post-impact",
            "leakage_risk": "High",
            "in_primary_ranking": "No (ablation)",
        },
        {
            "variable": "Total Killed / Total Injured Form 57",
            "timing": "Outcome definition",
            "leakage_risk": "N/A (defines Y)",
            "in_primary_ranking": "No (outcome only)",
        },
        {
            "variable": "Narrative / text fields",
            "timing": "Post-event documentation",
            "leakage_risk": "High",
            "in_primary_ranking": "No (excluded)",
        },
        {
            "variable": "Visibility, weather, roadway",
            "timing": "Incident context",
            "leakage_risk": "Low–moderate",
            "in_primary_ranking": "Yes (context)",
        },
        {
            "variable": "Estimated vehicle / train speed",
            "timing": "Mixed (often pre-impact)",
            "leakage_risk": "Moderate",
            "in_primary_ranking": "H2; optional ML",
        },
        {
            "variable": "User age, sex, action",
            "timing": "Mixed",
            "leakage_risk": "Low–moderate",
            "in_primary_ranking": "Yes (with missingness)",
        },
        {
            "variable": "Warning device fields",
            "timing": "Inventory / device (partially pre-event)",
            "leakage_risk": "Moderate (not in core set)",
            "in_primary_ranking": "Full model only",
        },
    ]


def gini_coefficient(values: np.ndarray) -> float:
    x = np.sort(values[values > 0])
    if len(x) == 0:
        return 0.0
    n = len(x)
    cum = np.cumsum(x)
    return float((n + 1 - 2 * np.sum(cum) / cum[-1]) / n)


def h2_interaction(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["Estimated Vehicle Speed", "Visibility"]).copy()
    d["S"] = pd.to_numeric(d["Estimated Vehicle Speed"], errors="coerce")
    d["V"] = d["low_vis"]
    d["Yv"] = d["Y"]
    d = d.dropna(subset=["S"])
    formula = (
        "Yv ~ S + V + S:V + Year + "
        "C(Q('State Name'), Treatment(reference='CALIFORNIA'))"
    )
    yv, Xv = patsy.dmatrices(formula, d, return_type="dataframe")
    fit = sm.Logit(yv, Xv).fit(disp=0, cov_type="cluster", cov_kwds={"groups": d["State Name"]})
    out = {}
    for term in ["S", "V", "S:V"]:
        if term in fit.params:
            out[term] = {
                "coef": float(fit.params[term]),
                "or": float(np.exp(fit.params[term])),
                "pvalue": float(fit.pvalues[term]),
            }
    # crossing-clustered sensitivity
    fit_x = sm.Logit(yv, Xv).fit(
        disp=0, cov_type="cluster", cov_kwds={"groups": d["Grade Crossing ID"]}
    )
    if "S:V" in fit_x.params:
        out["S:V_crossing_cluster"] = {
            "coef": float(fit_x.params["S:V"]),
            "pvalue": float(fit_x.pvalues["S:V"]),
        }
    out["n"] = int(len(d))
    return out


def rolling_origin_cv(df: pd.DataFrame) -> list[dict]:
    years = sorted(df["Year"].dropna().unique())
    rows = []
    pipe = hgb_pipeline(CAT, NUM)
    for test_year in years:
        if test_year < 2015:
            continue
        tr = df[df["Year"] < test_year]
        te = df[df["Year"] == test_year]
        if len(te) < 30 or tr["Y"].nunique() < 2:
            continue
        m = clone(pipe)
        m.fit(tr[CAT + NUM], tr["Y"])
        p = m.predict_proba(te[CAT + NUM])[:, 1]
        rows.append(
            {
                "test_year": int(test_year),
                "n_train": int(len(tr)),
                "n_test": int(len(te)),
                "auprc": float(average_precision_score(te["Y"], p)),
                "log_loss": float(log_loss(te["Y"], p, labels=[0, 1])),
            }
        )
    return rows


def national_comparison() -> dict:
    usecols = ["State Name", "Date", "Total Killed Form 57", "Total Injured Form 57"]
    raw = pd.read_csv(FRA, usecols=usecols, low_memory=False)
    raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
    raw = raw[(raw["Date"] >= "2013-01-01") & (raw["Date"] <= "2026-12-31")]
    raw["State Name"] = raw["State Name"].astype(str).str.strip().str.upper()
    k = raw["Total Killed Form 57"].fillna(0)
    j = raw["Total Injured Form 57"].fillna(0)
    raw["Y"] = ((k >= 1) | (j >= 1)).astype(int)
    study = {"CALIFORNIA", "GEORGIA", "MINNESOTA", "NEW JERSEY", "TEXAS", "WISCONSIN"}
    six = raw[raw["State Name"].isin(study)]
    return {
        "national_n": int(len(raw)),
        "national_harm_rate": float(raw["Y"].mean()),
        "six_state_n": int(len(six)),
        "six_state_harm_rate": float(six["Y"].mean()),
        "texas_share_national": float((raw["State Name"] == "TEXAS").mean()),
        "texas_share_six_state": float((six["State Name"] == "TEXAS").mean()),
    }


def vif_table(df: pd.DataFrame) -> dict:
    nums = df[["Year", "Temperature", "Vehicle Damage Cost", "User Age"]].copy()
    nums = nums.apply(pd.to_numeric, errors="coerce")
    nums = nums.dropna()
    if len(nums) < 100:
        return {}
    X = sm.add_constant(nums)
    out = {}
    for i, col in enumerate(nums.columns, start=1):
        y = X.iloc[:, i]
        Xo = X.drop(columns=[col])
        r2 = sm.OLS(y, Xo).fit().rsquared
        out[col] = float(1 / (1 - r2)) if r2 < 1 else float("inf")
    return out


def permutation_importance_top(df: pd.DataFrame, n_repeats: int = 10) -> dict:
    tr, te = StratifiedKFold(n_splits=5, shuffle=True, random_state=42).split(df, df["Y"]).__next__()
    train, test = df.iloc[tr], df.iloc[te]
    pre = make_preprocessor(CAT, NUM)
    rf = Pipeline(
        [
            ("pre", pre),
            (
                "m",
                RandomForestClassifier(
                    n_estimators=80,
                    max_depth=14,
                    min_samples_leaf=6,
                    class_weight="balanced_subsample",
                    random_state=RANDOM_STATE,
                    n_jobs=1,
                ),
            ),
        ]
    )
    rf.fit(train[CAT + NUM], train["Y"])
    r = permutation_importance(
        rf, test[CAT + NUM], test["Y"], n_repeats=n_repeats, random_state=RANDOM_STATE, n_jobs=1
    )
    # feature names after transform
    names = rf.named_steps["pre"].get_feature_names_out()
    order = np.argsort(r.importances_mean)[::-1][:12]
    return {
        "top_features": [
            {"feature": str(names[i]), "importance_mean": float(r.importances_mean[i])}
            for i in order
        ]
    }


def temporal_recurrence_harm(df: pd.DataFrame) -> dict:
    """
    Crossing-year consecutive pairs (t, t+1 calendar years).
    P(Y_{t+1}=1) = Pr(any harm in year t+1 | condition on year-t activity).
    """
    d = df.dropna(subset=["Date", "Grade Crossing ID"]).copy()
    d["year"] = d["Date"].dt.year.astype(int)
    cy = (
        d.groupby(["Grade Crossing ID", "year"], as_index=False)
        .agg(n_t=("Y", "count"), y_t=("Y", "max"))
        .rename(columns={"y_t": "harm_t"})
    )
    pairs: list[dict] = []
    cum_pairs: list[dict] = []
    for _, g in cy.groupby("Grade Crossing ID"):
        g = g.sort_values("year").reset_index(drop=True)
        cum_n = 0
        for i in range(len(g) - 1):
            if int(g.loc[i + 1, "year"]) != int(g.loc[i, "year"]) + 1:
                continue
            cum_n += int(g.loc[i, "n_t"])
            pairs.append(
                {
                    "n_t": int(g.loc[i, "n_t"]),
                    "harm_t": int(g.loc[i, "harm_t"]),
                    "y_t1": int(g.loc[i + 1, "harm_t"]),
                }
            )
            cum_pairs.append({"cum_n_through_t": cum_n, "y_t1": int(g.loc[i + 1, "harm_t"])})
    pdf = pd.DataFrame(pairs)
    cdf = pd.DataFrame(cum_pairs)
    overall_t1 = float(pdf["y_t1"].mean()) if len(pdf) else None

    def cond_rate(frame: pd.DataFrame, mask) -> dict:
        sub = frame[mask]
        return {
            "n_pairs": int(len(sub)),
            "p_harm_year_t_plus_1": float(sub["y_t1"].mean()) if len(sub) else None,
        }

    by_n_t: dict[str, dict] = {}
    for k in [1, 2, 3]:
        by_n_t[str(k)] = cond_rate(pdf, pdf["n_t"] >= k)
    by_n_t["baseline_any_incident_t"] = cond_rate(pdf, pdf["n_t"] >= 1)
    by_n_t["single_incident_t"] = cond_rate(pdf, pdf["n_t"] == 1)

    by_cum: dict[str, dict] = {}
    for k in [2, 3, 4]:
        by_cum[str(k)] = cond_rate(cdf, cdf["cum_n_through_t"] >= k)

    by_harm_t = {
        "harm_in_year_t": cond_rate(pdf, pdf["harm_t"] == 1),
        "no_harm_in_year_t_but_incident": cond_rate(
            pdf, (pdf["harm_t"] == 0) & (pdf["n_t"] >= 1)
        ),
    }

    return {
        "definition": "Consecutive calendar-year pairs at the same Grade Crossing ID; Y_{t+1}=1 if any injury/fatality in year t+1.",
        "n_consecutive_pairs": int(len(pdf)),
        "unconditional_p_harm_t_plus_1": overall_t1,
        "by_incidents_in_year_t": by_n_t,
        "by_cumulative_incidents_through_t": by_cum,
        "by_harm_in_year_t": by_harm_t,
    }


def visibility_crude_table(df: pd.DataFrame) -> dict:
    rows = {}
    for lab in ["Dark", "Day", "Dusk", "Dawn"]:
        m = df["Visibility"] == lab
        if m.sum():
            rows[lab] = {
                "n": int(m.sum()),
                "harm_rate": float(df.loc[m, "Y"].mean()),
            }
    return rows


def main() -> None:
    print("Loading cohort...", flush=True)
    df = load_df()
    gid_counts = df.groupby("Grade Crossing ID").size()

    results: dict = {
        "cohort_n": int(len(df)),
        "harm_rate": float(df["Y"].mean()),
    }

    print("H1 state-cluster bootstrap OR (B=2000)...", flush=True)
    results["h1_bootstrap_or"] = bootstrap_h1_or(df, "Y")
    results["h1_fatal_only_bootstrap_or"] = bootstrap_h1_or(df, "Y_fat") if df["Y_fat"].sum() > 50 else {}
    results["h1_injury_only_bootstrap_or"] = bootstrap_h1_or(df, "Y_inj_only")

    print("H1 wild-cluster bootstrap + HC3...", flush=True)
    results["h1_wild_cluster"] = wild_cluster_bootstrap_h1(df, "Y")

    print("H3 crossing-bootstrap rho + Gini...", flush=True)
    results["h3_rho_bootstrap"] = {
        "k2": bootstrap_rho_crossing(df, "Y", 2),
        "k3": bootstrap_rho_crossing(df, "Y", 3),
        "k4": bootstrap_rho_crossing(df, "Y", 4),
    }
    results["gini_bootstrap"] = bootstrap_gini_crossing(df)
    results["h3_null_rho_permutation"] = null_rho_permutation(df, "Y", 2, n_sim=5000)
    gini_pt = gini_coefficient(gid_counts.values)
    results["recurrence_descriptives"] = {
        "distinct_crossings": int(gid_counts.shape[0]),
        "crossings_ge2": int((gid_counts >= 2).sum()),
        "crossings_ge3": int((gid_counts >= 3).sum()),
        "gini_incident_counts": float(gini_pt),
        "pct_incidents_at_repeat_k2": float((df["Grade Crossing ID"].map(gid_counts) >= 2).mean()),
    }

    print("H2 interaction...", flush=True)
    results["h2_speed_visibility"] = h2_interaction(df)

    print("CV ablation (no damage cost)...", flush=True)
    results["cv_full"] = cv_metrics(df, "Y", CAT, NUM)
    results["cv_no_damage_cost"] = cv_metrics(df, "Y", CAT, NUM_NO_DAMAGE)
    results["cv_fatal_only"] = cv_metrics(df, "Y_fat", CAT, NUM)
    results["cv_injury_only"] = cv_metrics(df, "Y_inj_only", CAT, NUM)

    print("Rolling-origin CV...", flush=True)
    ro = rolling_origin_cv(df)
    results["rolling_origin"] = {
        "folds": ro,
        "mean_auprc": float(np.mean([x["auprc"] for x in ro])) if ro else None,
        "mean_log_loss": float(np.mean([x["log_loss"] for x in ro])) if ro else None,
    }
    print("Rolling-origin unseen-crossing holdout...", flush=True)
    results["rolling_origin_unseen_crossings"] = rolling_origin_unseen_crossings(df)

    print("Missingness diagnostics...", flush=True)
    results["missingness"] = missingness_diagnostics(df)
    results["california_audit"] = california_fatality_audit(df)
    results["leakage_audit"] = leakage_audit_rows()

    print("National comparison...", flush=True)
    results["national_comparison"] = national_comparison()

    print("VIF...", flush=True)
    results["vif_core_numerics"] = vif_table(df)

    print("Permutation importance...", flush=True)
    results["permutation_importance"] = permutation_importance_top(df)

    print("Visibility strata...", flush=True)
    results["visibility_harm_rates"] = visibility_crude_table(df)

    # H1 state-stratified dark prevalence
    st = {}
    for s, g in df.groupby("State Name"):
        if len(g) > 50:
            md = g["Visibility"] == "Dark"
            mv = g["Visibility"] == "Day"
            st[s] = {
                "dark_harm": float(g.loc[md, "Y"].mean()) if md.any() else None,
                "day_harm": float(g.loc[mv, "Y"].mean()) if mv.any() else None,
            }
    results["state_visibility_harm"] = st

    # Chi2 dark vs day
    sub = df[df["Visibility"].isin(["Dark", "Day"])]
    tab = pd.crosstab(sub["Visibility"], sub["Y"])
    chi2, p, _, _ = stats.chi2_contingency(tab)
    results["h1_chi2_dark_day"] = {"chi2": float(chi2), "p": float(p), "n": int(len(sub))}

    print("Pareto / weighting / winsor / model comparison...", flush=True)
    results["pareto"] = pareto_top_decile_harm_share(df)
    results["state_weighted_harm"] = state_weighted_harm_rate(df)
    wdf, cap99 = winsor_damage_cost(df)
    results["winsor_damage_99"] = {
        "cap_usd": cap99,
        "n_capped": int(
            (pd.to_numeric(df["Vehicle Damage Cost"], errors="coerce") > cap99).sum()
        ),
        "cv_full": cv_metrics(df, "Y", CAT, NUM),
        "cv_winsor": cv_metrics(wdf, "Y", CAT, NUM),
    }
    results["model_auprc_comparison"] = model_auprc_fold_bootstrap(df)
    cc = df["User Age"].notna()
    results["complete_case_user_age"] = {
        "n": int(cc.sum()),
        "harm_rate": float(df.loc[cc, "Y"].mean()),
        "h1_or": bootstrap_h1_or(df.loc[cc], "Y"),
    }

    print("Temporal recurrence P(Y_{t+1})...", flush=True)
    results["temporal_recurrence"] = temporal_recurrence_harm(df)

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()

