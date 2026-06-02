#Requires -Version 7.0
<#
.SYNOPSIS
    Baut CostCenter.exe aus den Python-Quelldateien (PyInstaller).

.DESCRIPTION
    Installiert fehlende Dependencies und erstellt eine portable Einzel-EXE
    mit PyInstaller. Die fertige Datei liegt unter: dist\CostCenter.exe

.EXAMPLE
    .\build_exe.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step  { param([string]$T) Write-Host "`n[$([char]0x25B6)] $T" -ForegroundColor Cyan }
function Write-OK    { param([string]$T) Write-Host "  [OK] $T" -ForegroundColor Green }
function Write-Warn  { param([string]$T) Write-Host "  [!]  $T" -ForegroundColor Yellow }

# ── Verzeichnis prüfen ────────────────────────────────────────────────────────
if (-not (Test-Path "gui.py")) {
    Write-Error "Bitte im CostCenter-Projektordner ausführen (wo gui.py liegt)."
    exit 1
}

# ── Dependencies installieren ─────────────────────────────────────────────────
Write-Step "Python-Pakete prüfen und installieren..."

$packages = @("customtkinter", "pyinstaller", "azure-identity", "requests", "openpyxl", "python-dotenv")
foreach ($pkg in $packages) {
    $installed = pip show $pkg 2>$null
    if (-not $installed) {
        Write-Host "  Installiere: $pkg" -ForegroundColor Gray
        pip install $pkg --quiet
    } else {
        Write-OK "$pkg vorhanden"
    }
}

# ── Alten Build aufräumen ─────────────────────────────────────────────────────
Write-Step "Alten Build aufräumen..."
foreach ($dir in @("build", "dist")) {
    if (Test-Path $dir) {
        Remove-Item $dir -Recurse -Force
        Write-OK "Ordner entfernt: $dir"
    }
}
if (Test-Path "CostCenter.spec") {
    Remove-Item "CostCenter.spec" -Force
}

# ── CustomTkinter Pfad ermitteln (für --add-data) ─────────────────────────────
Write-Step "CustomTkinter-Pfad ermitteln..."
$ctk_path = python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))" 2>$null
if (-not $ctk_path) {
    Write-Error "CustomTkinter konnte nicht gefunden werden. Bitte 'pip install customtkinter' ausführen."
    exit 1
}
Write-OK "CustomTkinter: $ctk_path"

# ── PyInstaller aufrufen ──────────────────────────────────────────────────────
Write-Step "PyInstaller – EXE wird gebaut (dauert 1–3 Minuten)..."

$addData = @(
    "--add-data", "$ctk_path;customtkinter",
    "--add-data", "src;src"
)

$pyinstallerArgs = @(
    "gui.py",
    "--onefile",
    "--windowed",
    "--noupx",
    "--name", "CostCenter",
    "--distpath", "dist",
    "--workpath", "build"
) + $addData

# Optionales Icon (wenn vorhanden)
if (Test-Path "costcenter.ico") {
    $pyinstallerArgs += @("--icon", "costcenter.ico")
    Write-OK "Icon gefunden: costcenter.ico"
} else {
    Write-Warn "Kein Icon (costcenter.ico) gefunden – wird ohne Icon gebaut."
}

python -m PyInstaller @pyinstallerArgs

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller ist fehlgeschlagen (Exit Code: $LASTEXITCODE)"
    exit 1
}

# ── Ergebnis prüfen ───────────────────────────────────────────────────────────
$exePath = "dist\CostCenter.exe"
if (Test-Path $exePath) {
    $size = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  Build erfolgreich!" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Datei  : $((Resolve-Path $exePath).Path)" -ForegroundColor White
    Write-Host "  Größe  : $size MB" -ForegroundColor White
    Write-Host ""
    Write-Host "  Verteilung: Nur diese eine .exe weitergeben!" -ForegroundColor Yellow
    Write-Host ""

    # EXE direkt starten?
    $answer = Read-Host "  EXE jetzt starten? (j/n)"
    if ($answer -eq "j") {
        Start-Process $exePath
    }
} else {
    Write-Error "EXE nicht gefunden – Build vermutlich fehlgeschlagen."
    exit 1
}
