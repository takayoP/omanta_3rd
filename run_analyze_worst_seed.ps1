# ワーストseed分析実行スクリプト（PowerShell）

Write-Host "==================================================================================" -ForegroundColor Cyan
Write-Host "ワーストseed詳細分析" -ForegroundColor Cyan
Write-Host "==================================================================================" -ForegroundColor Cyan
Write-Host ""

# seed耐性テスト結果ファイルの存在確認
$robustnessFile = "seed_robustness_test_result.json"
if (-not (Test-Path $robustnessFile)) {
    Write-Host "エラー: seed耐性テスト結果ファイルが見つかりません: $robustnessFile" -ForegroundColor Red
    Write-Host "先に seed耐性テストを実行してください。" -ForegroundColor Yellow
    exit 1
}

# seed番号を指定（デフォルト: 4）
$seed = 4
if ($args.Count -gt 0) {
    $seed = [int]$args[0]
}

Write-Host "分析対象seed: $seed" -ForegroundColor Cyan
Write-Host ""

# 分析実行
python analyze_worst_seed.py `
    --seed-robustness-json seed_robustness_test_result.json `
    --seed $seed `
    --json-file optimization_result_optimization_longterm_studyC_20260102_205614.json `
    --start 2020-01-01 `
    --end 2022-12-31

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==================================================================================" -ForegroundColor Green
    Write-Host "✓ 分析が正常に完了しました" -ForegroundColor Green
    Write-Host "==================================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "結果ファイル: worst_seed_${seed}_analysis.json" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "==================================================================================" -ForegroundColor Red
    Write-Host "✗ 分析実行中にエラーが発生しました" -ForegroundColor Red
    Write-Host "==================================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "エラーコード: $LASTEXITCODE" -ForegroundColor Red
}



