# 分割seed耐性テスト実行スクリプト（PowerShell）

Write-Host "==================================================================================" -ForegroundColor Cyan
Write-Host "分割seed耐性テスト実行" -ForegroundColor Cyan
Write-Host "==================================================================================" -ForegroundColor Cyan
Write-Host ""

# キャッシュファイルが破損している可能性があるため、削除
$cacheFile = "cache\features\features_2020-01-31_2022-12-30_v1.parquet"
if (Test-Path $cacheFile) {
    Write-Host "破損した可能性のあるキャッシュファイルを削除します..." -ForegroundColor Yellow
    Remove-Item -Path $cacheFile -Force -ErrorAction SilentlyContinue
    Write-Host "✓ キャッシュファイルを削除しました" -ForegroundColor Green
    Write-Host ""
}

# テスト実行
Write-Host "分割seed耐性テストを実行します..." -ForegroundColor Cyan
Write-Host "  これには時間がかかります（20回のテスト実行）" -ForegroundColor Yellow
Write-Host ""

python test_split_seed_robustness.py `
    --json-file optimization_result_optimization_longterm_studyC_20260102_205614.json `
    --start 2020-01-01 `
    --end 2022-12-31 `
    --n-seeds 20 `
    --train-ratio 0.8 `
    --output seed_robustness_test_result.json

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==================================================================================" -ForegroundColor Green
    Write-Host "✓ テストが正常に完了しました" -ForegroundColor Green
    Write-Host "==================================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "結果ファイル: seed_robustness_test_result.json" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "==================================================================================" -ForegroundColor Red
    Write-Host "✗ テスト実行中にエラーが発生しました" -ForegroundColor Red
    Write-Host "==================================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "エラーコード: $LASTEXITCODE" -ForegroundColor Red
}















