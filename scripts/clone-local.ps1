# Clone Heritage Short to Henok's local Windows folder
# Run in PowerShell:
#
#   powershell -ExecutionPolicy Bypass -File scripts/clone-local.ps1
#
# Target (from project preferences): D:\10X\AI-Content Generation

$ErrorActionPreference = "Stop"
$Target = "D:\10X\AI-Content Generation"
$Repo = "https://github.com/henask12/heritage-short.git"

New-Item -ItemType Directory -Force -Path "D:\10X" | Out-Null

if (Test-Path (Join-Path $Target ".git")) {
  Write-Host "Repo already present at $Target — pulling latest main..."
  Set-Location $Target
  git fetch origin
  git checkout main
  git pull origin main
} elseif (Test-Path $Target) {
  $items = Get-ChildItem -Force $Target | Where-Object { $_.Name -notin @('.', '..') }
  if ($items) {
    Write-Host "Folder exists and is not empty: $Target"
    Write-Host "Clone into a subfolder instead, or empty it first."
    exit 1
  }
  git clone $Repo $Target
} else {
  git clone $Repo $Target
}

Set-Location $Target
if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env — add GEMINI_API_KEY (and later Cloudflare/Kaggle keys)."
}

Write-Host ""
Write-Host "Ready at $Target"
Write-Host "Run: make radio-cut   or   make film"
Write-Host "Finals: outputs\final\red-through-the-years-16x9.mp4 and *-9x16.mp4"
