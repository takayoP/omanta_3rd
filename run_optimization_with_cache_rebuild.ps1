# キャッシュ再構築付きで最適化を実行するスクリプト
# entry_score/core_scoreキャッシュ問題の修正を反映

Write-Host "========================================"
Write-Host "最適化実行（キャッシュ再構築付き）"
Write-Host "========================================"
Write-Host ""

# パラメータ設定
$startDate = "2018-01-31"
$endDate = "2024-12-31"
$studyType = "C"
$nTrials = 200
$trainEndDate = "2023-12-31"
$asOfDate = "2024-12-31"
$horizonMonths = 24
$lambdaPenalty = 0.00

Write-Host "パラメータ:"
Write-Host "  開始日: $startDate"
Write-Host "  終了日: $endDate"
Write-Host "  Studyタイプ: $studyType"
Write-Host "  試行回数: $nTrials"
Write-Host "  学習期間終了日: $trainEndDate"
Write-Host "  評価日: $asOfDate"
Write-Host "  ホライズン: $horizonMonths ヶ月"
Write-Host "  λ: $lambdaPenalty"
Write-Host ""

# 最適化を実行（キャッシュ再構築付き）
Write-Host "最適化を開始します（キャッシュ再構築付き）..."
Write-Host ""

python -m omanta_3rd.jobs.optimize_longterm `
  --start $startDate `
  --end $endDate `
  --study-type $studyType `
  --n-trials $nTrials `
  --train-end-date $trainEndDate `
  --as-of-date $asOfDate `
  --horizon-months $horizonMonths `
  --lambda-penalty $lambdaPenalty `
  --force-rebuild-cache

Write-Host ""
Write-Host "最適化が完了しました。"

