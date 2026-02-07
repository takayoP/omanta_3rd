# Gate 1: 再現性チェック（PowerShellラッパー）

# デフォルト設定
$initialParamsJson = "optimization_result_optimization_longterm_studyA_20260121_204615.json"
$seeds = "42,123,456,789,999"
$nTrials = 100
$tolerance = 1.0

# 引数処理
if ($args.Count -gt 0) {
    $initialParamsJson = $args[0]
}
if ($args.Count -gt 1) {
    $seeds = $args[1]
}
if ($args.Count -gt 2) {
    $nTrials = [int]$args[2]
}
if ($args.Count -gt 3) {
    $tolerance = [double]$args[3]
}

Write-Host "=================================================================================="
Write-Host "Gate 1: 再現性チェック"
Write-Host "=================================================================================="
Write-Host ""
Write-Host "初期パラメータ: $initialParamsJson"
Write-Host "Seed: $seeds"
Write-Host "各seedでの試行回数: $nTrials"
Write-Host "許容されるブレ: ±$tolerance%ポイント"
Write-Host ""

# Pythonスクリプトを実行
python scripts/gate1_reproducibility_check.py `
  --initial-params-json $initialParamsJson `
  --seeds $seeds `
  --n-trials $nTrials `
  --tolerance $tolerance

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Gate 1 が失敗しました"
    exit 1
} else {
    Write-Host ""
    Write-Host "✅ Gate 1 が成功しました"
    exit 0
}
