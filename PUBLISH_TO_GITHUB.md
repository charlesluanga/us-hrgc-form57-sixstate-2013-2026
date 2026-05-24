# Publish to GitHub

1. Open **this folder only** in VS Code:  
   `United States Data\data_sharing`

2. Run the assembly script from the **private** project root:

```powershell
powershell -File "..\data_sharing\prepare_github_release.ps1"
```

3. Initialize git **inside `data_sharing/`** (if not already):

```powershell
git init
git add .
git status   # confirm no manuscript/reviews/*.docx paths appear
git commit -m "Six-state FRA Form 57 cohort and replication scripts"
```

4. Create public repo **`us-hrgc-form57-sixstate-2013-2026`** on GitHub and push.

5. Update `manuscript/CODE_REPOSITORY_URL.txt` if the URL changes, then:

```powershell
python manuscript/scripts/assemble_full_manuscript.py
```

**Never push:** parent `manuscript/`, `reviews/`, Word/PDF exports, or FRA bulk CSV.
