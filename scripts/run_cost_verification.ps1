# コスト効き確認
# usage: .\scripts\run_cost_verification.ps1

$paramsJson = "optimization_result_optimization_longterm_studyA_local_20260201_132836.json"
$testPeriod = "2022"

Write-Host "コスト効き確認を実行します..."
Write-Host "  params: $paramsJson"
Write-Host "  period: $testPeriod"
Write-Host ""

python scripts/verify_cost_application.py `
  --params-json $paramsJson `
  --cost-bps-list "0,10,25,50" `
  --test-period $testPeriod
