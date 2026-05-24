# Software environment

| Component | Version |
|-----------|---------|
| Python | 3.12.8 |
| pandas | 2.3.0 |
| numpy | 2.2.6 |
| scikit-learn | 1.7.0 |
| scipy | 1.16.0 |
| statsmodels | 0.14.5 |
| matplotlib | 3.10.3 |
| shap | 0.47.2 |
| openpyxl | 3.1.5 |

Install: `pip install -r requirements.txt`

## Random seeds

- **42** — stratified 3-fold CV, random forest, histgradient boosting, bootstrap resamples (`run_revision_analyses.py`).

## OS tested

Windows 11; scripts use `pathlib` and should run on macOS/Linux with path adjustments only for optional FRA CSV location.
