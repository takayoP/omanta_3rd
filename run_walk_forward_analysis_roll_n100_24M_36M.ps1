# Walk-Forward Analysis実行スクリプト（n_trials=100、24M/36M同時実行）
# 逆張り許可設計で24M/36Mのrollテストを同時に実行します（試行回数100）

Write-Host ("=" * 80)
Write-Host "Walk-Forward Analysis 実行（n_trials=100、24M/36M同時実行）"
Write-Host ("=" * 80)
Write-Host ""

# パラメータ設定
$START_DATE = "2020-01-01"
$END_DATE = "2025-12-31"
$TRAIN_MIN_YEARS = 2.0
$N_TRIALS = 100  # 再現性確認のため100に設定
$STUDY_TYPE = "C"
$HOLDOUT_EVAL_YEAR = 2025
$FOLD_TYPE = "roll"
$SEED = 42
$N_JOBS_FOLD = 1
$N_JOBS_OPTUNA = 1

Write-Host "設定:"
Write-Host "  期間: $START_DATE ～ $END_DATE"
Write-Host "  ホライズン: 24M / 36M（同時実行）"
Write-Host "  Foldタイプ: $FOLD_TYPE"
Write-Host "  最小Train期間: $TRAIN_MIN_YEARS 年"
Write-Host "  最適化試行回数: $N_TRIALS（再現性確認のため増加）"
Write-Host "  スタディタイプ: $STUDY_TYPE"
Write-Host "  評価終了年ホールドアウト: $HOLDOUT_EVAL_YEAR"
Write-Host "  乱数シード: $SEED"
Write-Host "  Fold間並列数: $N_JOBS_FOLD"
Write-Host "  Optuna並列数: $N_JOBS_OPTUNA"
Write-Host ""

Write-Host "【期待される成果物】"
Write-Host "  1. walk_forward_longterm_24M_roll_evalYear2025.json"
Write-Host "  2. walk_forward_longterm_36M_roll_evalYear2025.json"
Write-Host "  3. params_by_fold_24M.json / params_by_fold_36M.json"
Write-Host "  4. params_operational_24M.json / params_operational_36M.json"
Write-Host ""

# 24M用のコマンド
$cmd24M = @(
    "python",
    "walk_forward_longterm.py",
    "--start", $START_DATE,
    "--end", $END_DATE,
    "--horizon", "24",
    "--train-min-years", [string]$TRAIN_MIN_YEARS,
    "--n-trials", [string]$N_TRIALS,
    "--study-type", $STUDY_TYPE,
    "--holdout-eval-year", [string]$HOLDOUT_EVAL_YEAR,
    "--fold-type", $FOLD_TYPE,
    "--seed", [string]$SEED,
    "--n-jobs-fold", [string]$N_JOBS_FOLD,
    "--n-jobs-optuna", [string]$N_JOBS_OPTUNA
)

# 36M用のコマンド
$cmd36M = @(
    "python",
    "walk_forward_longterm.py",
    "--start", $START_DATE,
    "--end", $END_DATE,
    "--horizon", "36",
    "--train-min-years", [string]$TRAIN_MIN_YEARS,
    "--n-trials", [string]$N_TRIALS,
    "--study-type", $STUDY_TYPE,
    "--holdout-eval-year", [string]$HOLDOUT_EVAL_YEAR,
    "--fold-type", $FOLD_TYPE,
    "--seed", [string]$SEED,
    "--n-jobs-fold", [string]$N_JOBS_FOLD,
    "--n-jobs-optuna", [string]$N_JOBS_OPTUNA
)

Write-Host "実行コマンド（24M）:"
Write-Host ($cmd24M -join " ")
Write-Host ""
Write-Host "実行コマンド（36M）:"
Write-Host ($cmd36M -join " ")
Write-Host ""
Write-Host ("=" * 80)
Write-Host ""

# ログファイル名（タイムスタンプ付き）
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log24M = "walk_forward_24M_n100_$timestamp.log"
$log36M = "walk_forward_36M_n100_$timestamp.log"

Write-Host "ログファイル:"
Write-Host "  24M: $log24M"
Write-Host "  36M: $log36M"
Write-Host ""

# バックグラウンドジョブとして実行
Write-Host "24Mと36Mのテストを同時に開始します..."
Write-Host ""

# 作業ディレクトリを保存
$workingDir = (Get-Location).Path

# コマンドを文字列として構築（配列展開の問題を回避）
$cmd24MStr = ($cmd24M | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }) -join ' '
$cmd36MStr = ($cmd36M | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }) -join ' '

$job24M = Start-Job -ScriptBlock {
    param($cmdStr, $logFile, $workDir)
    Set-Location $workDir
    Invoke-Expression "$cmdStr *> $logFile"
} -ArgumentList $cmd24MStr, $log24M, $workingDir

$job36M = Start-Job -ScriptBlock {
    param($cmdStr, $logFile, $workDir)
    Set-Location $workDir
    Invoke-Expression "$cmdStr *> $logFile"
} -ArgumentList $cmd36MStr, $log36M, $workingDir

Write-Host "[OK] 両方のジョブを開始しました"
Write-Host ""
Write-Host "進行状況を監視中..."
Write-Host "（Ctrl+Cで中断できますが、ジョブはバックグラウンドで継続します）"
Write-Host ""

# 進行状況を監視
$startTime = Get-Date
while ($job24M.State -eq "Running" -or $job36M.State -eq "Running") {
    $elapsed = (Get-Date) - $startTime
    Write-Host "経過時間: $($elapsed.ToString('hh\:mm\:ss'))" -NoNewline
    Write-Host " | 24M: $($job24M.State) | 36M: $($job36M.State)"
    
    # ログの最後の数行を表示（進行状況確認）
    if (Test-Path $log24M) {
        $lastLines24M = Get-Content $log24M -Tail 1 -ErrorAction SilentlyContinue
        if ($lastLines24M) {
            Write-Host "  24M: $lastLines24M"
        }
    }
    if (Test-Path $log36M) {
        $lastLines36M = Get-Content $log36M -Tail 1 -ErrorAction SilentlyContinue
        if ($lastLines36M) {
            Write-Host "  36M: $lastLines36M"
        }
    }
    
    Start-Sleep -Seconds 30
}

# 結果を取得
Write-Host ""
Write-Host ("=" * 80)
Write-Host "実行結果"
Write-Host ("=" * 80)
Write-Host ""

$result24M = Receive-Job -Job $job24M
$result36M = Receive-Job -Job $job36M

Remove-Job -Job $job24M, $job36M

Write-Host "24Mテスト:"
if ($job24M.State -eq "Completed") {
    Write-Host "  [OK] 正常に完了しました"
} else {
    Write-Host "  [NG] エラーまたは中断されました（状態: $($job24M.State)）"
}
Write-Host "  ログ: $log24M"
Write-Host ""

Write-Host "36Mテスト:"
if ($job36M.State -eq "Completed") {
    Write-Host "  [OK] 正常に完了しました"
} else {
    Write-Host "  [NG] エラーまたは中断されました（状態: $($job36M.State)）"
}
Write-Host "  ログ: $log36M"
Write-Host ""

Write-Host ("=" * 80)
Write-Host "完了"
Write-Host ("=" * 80)

