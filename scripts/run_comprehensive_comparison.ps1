# 候補パラメータの包括的比較を実行するPowerShellスクリプト

# デフォルト設定
$jsonFiles = "optimization_result_optimization_longterm_studyA_local_20260201_132836.json,optimization_result_optimization_longterm_studyA_local_20260201_150906.json"
$costBpsList = "0,10,25,50"
$testPeriods = "2022,2021"

# 引数処理
if ($args.Count -gt 0) {
    $jsonFiles = $args[0]
}
if ($args.Count -gt 1) {
    $costBpsList = $args[1]
}
if ($args.Count -gt 2) {
    $testPeriods = $args[2]
}

Write-Host "=================================================================================="
Write-Host "候補パラメータの包括的比較"
Write-Host "=================================================================================="
Write-Host ""
Write-Host "JSONファイル: $jsonFiles"
Write-Host "コスト: $costBpsList bps"
Write-Host "期間: $testPeriods"
Write-Host ""

# Pythonスクリプトを実行
python scripts/compare_candidates_comprehensive.py `
  --json-files $jsonFiles `
  --cost-bps-list $costBpsList `
  --test-periods $testPeriods

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ エラーが発生しました"
    exit 1
} else {
    Write-Host ""
    Write-Host "✅ 比較が完了しました"
    exit 0
}
