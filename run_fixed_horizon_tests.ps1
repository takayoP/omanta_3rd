# 固定ホライズン版 seed耐性テスト実行スクリプト（PowerShell）
# 12M/24M/36Mの各ホライズンでテストを実行

Write-Host "==================================================================================" -ForegroundColor Cyan
Write-Host "固定ホライズン版 seed耐性テスト実行" -ForegroundColor Cyan
Write-Host "==================================================================================" -ForegroundColor Cyan
Write-Host ""

$jsonFile = "optimization_result_optimization_longterm_studyC_20260102_205614.json"
$startDate = "2020-01-01"
$endDate = "2022-12-31"
$nSeeds = 20
$trainRatio = 0.8

$horizons = @(12, 24, 36)

foreach ($horizon in $horizons) {
    Write-Host ""
    Write-Host "==================================================================================" -ForegroundColor Yellow
    Write-Host "ホライズン $horizon M のテストを実行します..." -ForegroundColor Yellow
    Write-Host "==================================================================================" -ForegroundColor Yellow
    Write-Host ""
    
    $outputFile = "seed_robustness_fixed_horizon_" + $horizon.ToString() + "M.json"
    
    python test_seed_robustness_fixed_horizon.py `
        --json-file $jsonFile `
        --start $startDate `
        --end $endDate `
        --horizon $horizon `
        --n-seeds $nSeeds `
        --train-ratio $trainRatio `
        --output $outputFile
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✓ ホライズン $horizon M のテストが完了しました" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "✗ ホライズン $horizon M のテストでエラーが発生しました" -ForegroundColor Red
        Write-Host "エラーコード: $LASTEXITCODE" -ForegroundColor Red
        Write-Host ""
        break
    }
}

Write-Host ""
Write-Host "==================================================================================" -ForegroundColor Green
Write-Host "すべてのホライズンテストが完了しました" -ForegroundColor Green
Write-Host "==================================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "結果ファイル:" -ForegroundColor Cyan
foreach ($horizon in $horizons) {
    $outputFile = "seed_robustness_fixed_horizon_" + $horizon.ToString() + "M.json"
    $msg = "  - " + $outputFile
    Write-Host $msg -ForegroundColor Cyan
}
