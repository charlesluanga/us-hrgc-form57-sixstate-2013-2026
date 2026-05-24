# Copy replication files from private workspace into data_sharing/ for GitHub upload.
# Policy: statistics + figure SCRIPTS only.
$ErrorActionPreference = "Stop"
$PrivateRoot = Split-Path -Parent $PSScriptRoot
$Pub = $PSScriptRoot

$dirs = @("data", "scripts", "outputs", "expected")
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Pub $d) | Out-Null
}

# Remove stale figure binaries from prior assemblies (scripts-only policy)
$staleFig = Join-Path $Pub "outputs\figures"
if (Test-Path $staleFig) {
    Remove-Item $staleFig -Recurse -Force
}
$staleConcept = Join-Path $Pub "scripts\build_conceptual_framework_figure.py"
if (Test-Path $staleConcept) {
    Remove-Item $staleConcept -Force
}
# --- Data ---
$dataSrc = Join-Path $PrivateRoot "csv"
$dataFiles = @(
    "cohort_manifest.json",
    "DATA_CHANGELOG.md",
    "cleaning_report.txt"
)
foreach ($f in $dataFiles) {
    Copy-Item (Join-Path $dataSrc $f) (Join-Path $Pub "data\$f") -Force
}
$allStates = Join-Path $dataSrc "all_states.csv"
if (Test-Path $allStates) {
    Copy-Item $allStates (Join-Path $Pub "data\all_states.csv") -Force
    Write-Host "Copied data/all_states.csv"
} else {
    Write-Warning "Missing csv/all_states.csv - run clean_hrgc.py first or copy manually."
}

# --- Scripts (root -> scripts/) ---
Copy-Item (Join-Path $PrivateRoot "clean_hrgc.py") (Join-Path $Pub "scripts\clean_hrgc.py") -Force

$analysisScripts = @(
    "run_revision_analyses.py",
    "build_manuscript_figures.py",
    "run_treeshap_analysis.py",
    "build_appendix_figures.py",
    "build_manuscript_tables_excel.py",
    "cv_metrics_io.py",
    "figure_style.py",
    "figure_paths.py",
    "label_supplementary_panels.py"
)
# Excluded: build_conceptual_framework_figure.py (author-designed Figure 1; not code-reproducible)
$srcScripts = Join-Path $PrivateRoot "manuscript\scripts"
foreach ($s in $analysisScripts) {
    $src = Join-Path $srcScripts $s
    if (Test-Path $src) {
        $dest = Join-Path $Pub "scripts\$s"
        Copy-Item $src $dest -Force
        $text = Get-Content $dest -Raw -Encoding UTF8
        $text = $text -replace 'ROOT / "csv"', 'ROOT / "data"'
        $text = $text -replace 'manuscript/exports', 'outputs'
        $text = $text -replace 'manuscript\\exports', 'outputs'
        $text = $text -replace 'manuscript/figures', 'outputs/figures'
        $text = $text -replace 'manuscript\\figures', 'outputs/figures'
        $text = $text -replace 'FIG_ROOT = ROOT / "manuscript" / "figures"', 'FIG_ROOT = ROOT / "outputs" / "figures"'
        $text = $text -replace 'parents\[2\]', 'parents[1]'
        Set-Content $dest $text -Encoding UTF8
    } else {
        Write-Warning "Missing $s"
    }
}

$clean = Join-Path $Pub "scripts\clean_hrgc.py"
if (Test-Path $clean) {
    $text = Get-Content $clean -Raw -Encoding UTF8
    $text = $text -replace 'ROOT = Path\(r"C:\\Users\\User\\OneDrive\\Documents\\United States Data"\)', 'ROOT = Path(__file__).resolve().parents[1]'
    $text = $text -replace 'OUT_DIR = ROOT / "csv"', 'OUT_DIR = ROOT / "data"'
    Set-Content $clean $text -Encoding UTF8
}

# verify_replication.py already lives in data_sharing/scripts/

# --- Precomputed statistics only (no figure PNG/PDF binaries) ---
$revJson = Join-Path $PrivateRoot "manuscript\exports\revision_results.json"
if (Test-Path $revJson) {
    Copy-Item $revJson (Join-Path $Pub "outputs\revision_results.json") -Force
    Write-Host "Copied outputs/revision_results.json"
}
Write-Host ""
Write-Host "Assembly complete: $Pub"
Write-Host "Review FILE_MANIFEST.md, then git add/commit from data_sharing/ only."
