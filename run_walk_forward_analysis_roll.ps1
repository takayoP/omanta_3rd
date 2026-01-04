# Walk-Forward Analysis実行スクリプト（Roll型）
# 複数foldでWalk-Forward検証を実行します（fold間並列化あり）

# パラメータ設定
$START_DATE = "2020-01-01"
$END_DATE = "2025-12-31"
$HORIZON = 12  # ホライズン（月数: 12, 24, 36）
$FOLDS = 3  # fold数（roll型の場合）
$TRAIN_MIN_YEARS = 2.0  # 最小Train期間（年）
$N_TRIALS = 50  # 最適化試行回数
$STUDY_TYPE = "C"  # スタディタイプ（A/B/C）
$FOLD_TYPE = "roll"  # foldタイプ（roll: 複数fold）
$SEED = 42  # 乱数シード（再現性のため）
$N_JOBS_FOLD = -1  # fold間の並列数（-1: 自動, 1: 逐次実行）

# 実行コマンド
Write-Host "==================================================================================" -ForegroundColor Cyan
Write-Host "Walk-Forward Analysis 実行（Roll型、fold間並列化あり）" -ForegroundColor Cyan
Write-Host "==================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "設定:" -ForegroundColor Yellow
Write-Host "  期間: $START_DATE ～ $END_DATE"
Write-Host "  ホライズン: ${HORIZON}ヶ月"
Write-Host "  Fold数: $FOLDS"
Write-Host "  最小Train期間: ${TRAIN_MIN_YEARS}年"
Write-Host "  最適化試行回数: $N_TRIALS"
Write-Host "  スタディタイプ: $STUDY_TYPE"
Write-Host "  Foldタイプ: $FOLD_TYPE"
Write-Host "  乱数シード: $SEED"
Write-Host "  Fold間並列数: $N_JOBS_FOLD（自動設定）"
Write-Host ""

# 実行
python walk_forward_longterm.py `
    --start $START_DATE `
    --end $END_DATE `
    --horizon $HORIZON `
    --folds $FOLDS `
    --train-min-years $TRAIN_MIN_YEARS `
    --n-trials $N_TRIALS `
    --study-type $STUDY_TYPE `
    --fold-type $FOLD_TYPE `
    --seed $SEED `
    --n-jobs-fold $N_JOBS_FOLD

# 終了コードを確認
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==================================================================================" -ForegroundColor Green
    Write-Host "✅ 実行が正常に完了しました" -ForegroundColor Green
    Write-Host "==================================================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "==================================================================================" -ForegroundColor Red
    Write-Host "❌ エラーが発生しました (終了コード: $LASTEXITCODE)" -ForegroundColor Red
    Write-Host "==================================================================================" -ForegroundColor Red
    exit $LASTEXITCODE
}



