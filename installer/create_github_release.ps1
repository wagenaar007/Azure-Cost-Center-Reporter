# GitHub Release erstellen + EXE hochladen
# Verwendung: .\create_github_release.ps1 -Token "ghp_DEIN_TOKEN_HIER"

param(
    [Parameter(Mandatory=$true)]
    [string]$Token
)

$owner    = "wagenaar007"
$repo     = "Azure-Cost-Center-Reporter"
$tag      = "v0.0.2"
$exePath  = "$PSScriptRoot\..\dist\CostCenter.exe"
$headers  = @{
    Authorization = "Bearer $Token"
    Accept        = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

Write-Host "Erstelle Release $tag ..." -ForegroundColor Cyan

$body = @{
    tag_name   = $tag
    name       = "Azure Cost Center Reporter v0.0.2"
    body       = @"
## v0.0.2

### Download
- **CostCenter.exe** – standalone Windows application, no installation required

### Changes
- Removed daily data sheet from Excel output
- Fixed 429 rate-limit handling: reads Azure clienttype-retry-after header correctly
- Cache: previous month only re-fetched after 4 hours
- Cache stored in %LOCALAPPDATA%\CostCenter\ instead of next to EXE
- Installer uses user-scope install paths (no admin rights required)

### Requirements
- Windows 10/11 (64-bit)
- Azure Service Principal with Cost Management Reader role
- See [SETUP_SERVICE_PRINCIPAL.md](https://github.com/wagenaar007/Azure-Cost-Center-Reporter/blob/master/SETUP_SERVICE_PRINCIPAL.md) for setup instructions
"@
    draft     = $false
    prerelease = $false
} | ConvertTo-Json -Depth 5

$release = Invoke-RestMethod `
    -Uri "https://api.github.com/repos/$owner/$repo/releases" `
    -Method POST `
    -Headers $headers `
    -Body $body `
    -ContentType "application/json"

Write-Host "Release erstellt: $($release.html_url)" -ForegroundColor Green

# EXE hochladen
if (-not (Test-Path $exePath)) {
    Write-Warning "EXE nicht gefunden: $exePath – bitte zuerst build_exe.ps1 ausführen."
    exit 1
}

Write-Host "Lade CostCenter.exe hoch ($([math]::Round((Get-Item $exePath).Length/1MB,1)) MB)..." -ForegroundColor Cyan

$uploadUrl = $release.upload_url -replace '\{.*\}', ''
$exeBytes  = [System.IO.File]::ReadAllBytes($exePath)

Invoke-RestMethod `
    -Uri "${uploadUrl}?name=CostCenter.exe&label=CostCenter.exe (Windows x64)" `
    -Method POST `
    -Headers $headers `
    -Body $exeBytes `
    -ContentType "application/octet-stream" | Out-Null

Write-Host ""
Write-Host "Fertig! Release: $($release.html_url)" -ForegroundColor Green
