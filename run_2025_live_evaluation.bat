@echo off
REM 2025年疑似ライブ評価実行バッチファイル
REM 
REM Usage:
REM   run_2025_live_evaluation.bat
REM   またはコストを指定:
REM   run_2025_live_evaluation.bat 10.0

setlocal

REM 引数からコストを取得（デフォルト: 10.0）
set COST_BPS=10.0
if not "%~1"=="" set COST_BPS=%~1

echo ========================================
echo 2025年疑似ライブ評価を開始します
echo ========================================
echo 候補ファイル: candidates_selected_2025_live.json
echo 出力ファイル: holdout_2025_live_10bps.json
echo Holdout期間: 2025-01-01 ～ 2025-12-31
echo 取引コスト: %COST_BPS% bps (片道)
echo ========================================
echo.

REM 候補ファイルの存在確認
if not exist "candidates_selected_2025_live.json" (
    echo [ERROR] 候補ファイルが見つかりません: candidates_selected_2025_live.json
    exit /b 1
)

REM Pythonスクリプトを実行
python evaluate_candidates_holdout.py ^
    --candidates candidates_selected_2025_live.json ^
    --holdout-start 2025-01-01 ^
    --holdout-end 2025-12-31 ^
    --cost-bps %COST_BPS% ^
    --output holdout_2025_live_10bps.json ^
    --use-cache

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo 評価が正常に完了しました
    echo ========================================
    if exist "holdout_2025_live_10bps.json" (
        echo 出力ファイル: holdout_2025_live_10bps.json
    )
) else (
    echo.
    echo [ERROR] スクリプトがエラーコード %ERRORLEVEL% で終了しました
    exit /b %ERRORLEVEL%
)

endlocal

