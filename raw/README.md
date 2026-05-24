# National FRA source file (not stored in repository)

Place the U.S. Department of Transportation open-data export here:

`Highway-Rail_Grade_Crossing_Incident_Data__Form_57_.csv` (~230 MB)

Rebuild:

```bash
pip install -r requirements.txt
python scripts/clean_hrgc.py
python scripts/verify_cohort.py
```

The file in `../data/all_states.csv` is the reference analytic cohort (**8,394** rows) produced with the rules in `../data/DATA_CHANGELOG.md`.
