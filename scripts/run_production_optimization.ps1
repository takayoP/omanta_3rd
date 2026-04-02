# 月次リバランス型・実運用向け最適化（5日間プラン用）
# usage: .\scripts\run_production_optimization.ps1
# ログを残す例: .\scripts\run_production_optimization.ps1 2>&1 | Tee-Object -FilePath logs\optimization_20250315.log

$ErrorActionPreference = "Stop"
$studyDate = Get-Date -Format "yyyyMMdd"
$studyName = "production_$studyDate"

# BLASスレッドを1に固定（並列時の過負荷防止）
$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:NUMEXPR_NUM_THREADS = "1"

Write-Host "=============================================="
Write-Host "Monthly rebalance production optimization"
Write-Host "=============================================="
Write-Host "  study-name: $studyName"
Write-Host "  period: 2021-01-01 ~ 2024-12-31"
Write-Host "  n-trials: 200"
Write-Host "  cost: 20 bps (one-way)"
Write-Host "  n-jobs: 4, bt-workers: 1"
Write-Host "=============================================="
Write-Host ""

# リポジトリルートに移動
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
Set-Location $rootDir

python -m omanta_3rd.jobs.optimize_timeseries `
  --start 2021-01-01 `
  --end 2024-12-31 `
  --n-trials 200 `
  --study-name $studyName `
  --parallel-mode trial `
  --n-jobs 4 `
  --bt-workers 1 `
  --cost 20 `
  --no-progress-window

Write-Host ""
Write-Host "Done. Check optimization_result_optimization_timeseries_$studyName.json"
