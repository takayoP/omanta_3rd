# 2021寄与分解
# usage: .\scripts\run_2021_contribution.ps1

$paramsJson = "optimization_result_optimization_longterm_studyA_local_20260201_132836.json"

Write-Host "2021寄与分解を実行します..."
Write-Host "  params: $paramsJson"
Write-Host ""

python scripts/analyze_2021_contribution.py --params-json $paramsJson --cost-bps 25
