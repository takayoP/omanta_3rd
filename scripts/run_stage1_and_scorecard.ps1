# Stage0 通過 9 本に対して Stage1（2021単年）→ 3年スコアカード を実行する。
# 前提: プロジェクトルートで DB が利用可能であること。
# 使い方: プロジェクトルートで .\scripts\run_stage1_and_scorecard.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$passed = @(
    "optimization_result_optimization_longterm_studyC_20260111_154617.json",
    "optimization_result_optimization_longterm_studyC_20260112_223150.json",
    "optimization_result_optimization_longterm_studyC_20260208_131248.json",
    "optimization_result_optimization_longterm_studyC_20260208_204808.json",
    "optimization_result_optimization_longterm_studyC_20260209_005707.json",
    "optimization_result_optimization_longterm_studyC_20260209_072127.json",
    "optimization_result_optimization_longterm_studyC_20260209_111318.json",
    "optimization_result_optimization_longterm_studyC_20260209_195419.json",
    "optimization_result_optimization_longterm_studyC_20260209_235448.json"
)
$existing = @($passed | Where-Object { Test-Path $_ })
if ($existing.Count -eq 0) {
    Write-Host "Stage0 通過 JSON が見つかりません。カレントを確認してください。"
    exit 1
}

Write-Host "Stage1: 2021 単年で stage1_discard を出力（$($existing.Count) 件）"
python scripts/build_year_scorecard.py --candidates @existing --years 2021 --cost-bps 25 --out scorecard_stage1_2021.csv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "3年スコアカード（2020/2021/2022）: Stage1 通過候補は手動で選び --candidates に指定してください。"
Write-Host "例: python scripts/build_year_scorecard.py --candidates <通過したJSON> --cost-bps 25 --out scorecard_3y.csv"
