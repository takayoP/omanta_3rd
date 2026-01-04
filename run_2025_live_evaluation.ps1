# 2025年疑似ライブ評価実行スクリプト
# 
# Usage:
#   .\run_2025_live_evaluation.ps1
#   または
#   PowerShell -ExecutionPolicy Bypass -File .\run_2025_live_evaluation.ps1

param(
    [double]$CostBps = 10.0,
    [switch]$Background = $false,
    [switch]$NoCache = $false
)

# スクリプトのディレクトリに移動
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 設定
$candidatesFile = "candidates_selected_2025_live.json"
$outputFile = "holdout_2025_live_10bps.json"
$holdoutStart = "2025-01-01"
$holdoutEnd = "2025-12-31"

# ログ関数
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN"  { "Yellow" }
        "INFO"  { "Cyan" }
        "SUCCESS" { "Green" }
        default { "White" }
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

# 開始
Write-Log "=== 2025年疑似ライブ評価を開始します ===" "INFO"
Write-Log "候補ファイル: $candidatesFile" "INFO"
Write-Log "出力ファイル: $outputFile" "INFO"
Write-Log "Holdout期間: $holdoutStart ～ $holdoutEnd" "INFO"
Write-Log "取引コスト: $CostBps bps (片道)" "INFO"

# 候補ファイルの存在確認
if (-not (Test-Path $candidatesFile)) {
    Write-Log "エラー: 候補ファイルが見つかりません: $candidatesFile" "ERROR"
    exit 1
}

# Pythonコマンドの構築
$pythonCmd = "python evaluate_candidates_holdout.py"
$pythonCmd += " --candidates $candidatesFile"
$pythonCmd += " --holdout-start $holdoutStart"
$pythonCmd += " --holdout-end $holdoutEnd"
$pythonCmd += " --cost-bps $CostBps"
$pythonCmd += " --output $outputFile"

if (-not $NoCache) {
    $pythonCmd += " --use-cache"
}

Write-Log "実行コマンド: $pythonCmd" "INFO"
Write-Log "" "INFO"

# バックグラウンド実行
if ($Background) {
    Write-Log "バックグラウンドモードで実行します..." "INFO"
    
    $job = Start-Job -ScriptBlock {
        param($cmd, $dir)
        Set-Location $dir
        Invoke-Expression $cmd
    } -ArgumentList $pythonCmd, $scriptDir
    
    Write-Log "ジョブID: $($job.Id)" "INFO"
    Write-Log "ジョブ状態: $($job.State)" "INFO"
    Write-Log "" "INFO"
    Write-Log "ジョブの状態を確認するには以下を実行してください:" "INFO"
    Write-Log "  Get-Job -Id $($job.Id)" "INFO"
    Write-Log "  Receive-Job -Id $($job.Id) -Keep" "INFO"
    Write-Log "" "INFO"
    Write-Log "ジョブを停止するには:" "INFO"
    Write-Log "  Stop-Job -Id $($job.Id)" "INFO"
    
    # ジョブを監視（オプション）
    Write-Log "ジョブの監視を開始します（Ctrl+Cで停止）..." "INFO"
    try {
        while ($job.State -eq "Running") {
            Start-Sleep -Seconds 5
            $job = Get-Job -Id $job.Id -ErrorAction SilentlyContinue
            if ($job -and $job.HasMoreData) {
                $output = Receive-Job -Job $job -Keep
                if ($output) {
                    Write-Host $output
                }
            }
        }
        
        # 最終出力を取得
        if ($job.State -eq "Completed") {
            Write-Log "ジョブが完了しました" "SUCCESS"
            $finalOutput = Receive-Job -Job $job
            Write-Host $finalOutput
            Remove-Job -Job $job
        } elseif ($job.State -eq "Failed") {
            Write-Log "ジョブが失敗しました" "ERROR"
            $errorOutput = Receive-Job -Job $job
            Write-Host $errorOutput
            Remove-Job -Job $job
            exit 1
        }
    }
    catch {
        Write-Log "ジョブ監視中にエラーが発生しました: $_" "ERROR"
    }
}
else {
    # フォアグラウンド実行
    Write-Log "フォアグラウンドモードで実行します..." "INFO"
    Write-Log "" "INFO"
    
    try {
        # Pythonスクリプトを実行
        Invoke-Expression $pythonCmd
        
        if ($LASTEXITCODE -eq 0) {
            Write-Log "" "INFO"
            Write-Log "=== 評価が正常に完了しました ===" "SUCCESS"
            
            # 出力ファイルの確認
            if (Test-Path $outputFile) {
                $fileInfo = Get-Item $outputFile
                Write-Log "出力ファイル: $outputFile" "SUCCESS"
                Write-Log "ファイルサイズ: $($fileInfo.Length) bytes" "INFO"
                Write-Log "最終更新: $($fileInfo.LastWriteTime)" "INFO"
            }
            else {
                Write-Log "警告: 出力ファイルが生成されませんでした" "WARN"
            }
        }
        else {
            Write-Log "エラー: スクリプトがエラーコード $LASTEXITCODE で終了しました" "ERROR"
            exit $LASTEXITCODE
        }
    }
    catch {
        Write-Log "エラー: 実行中に例外が発生しました: $_" "ERROR"
        exit 1
    }
}

Write-Log "=== スクリプトを終了します ===" "INFO"



