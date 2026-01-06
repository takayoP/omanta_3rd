#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Walk-Forward Analysis実行時間の見積もり
"""

# 診断結果から
TRIAL_TIME_SECONDS = 148.4  # 1 trialあたりの実行時間（秒）
TRIAL_TIME_MINUTES = TRIAL_TIME_SECONDS / 60  # 約2.5分

# roll方式の設定
N_TRIALS = 30
HORIZON_MONTHS = 12
START_DATE = "2020-01-01"
END_DATE = "2025-12-31"
HOLDOUT_EVAL_YEAR = 2025

# 評価終了年の推定
# 2020-01-31リバランス → 12M後 → 2021年評価完了
# 2021-01-31リバランス → 12M後 → 2022年評価完了
# ...
# 2024-01-31リバランス → 12M後 → 2025年評価完了
# 2025-01-31リバランス → 12M後 → 2026年評価完了（データ終端を超える）

# roll方式のfold数推定
# 評価終了年が2021, 2022, 2023, 2024, 2025の5年分
# holdout_eval_year=2025未満の年: [2021, 2022, 2023, 2024]
# 中間fold: 4個（2021, 2022, 2023, 2024をテスト）
# 最終ホールドアウト: 1個（2025をテスト）
ESTIMATED_FOLDS = 5  # 4個の中間fold + 1個の最終ホールドアウト

print("=" * 80)
print("Walk-Forward Analysis 実行時間見積もり（roll方式）")
print("=" * 80)
print()
print("【設定】")
print(f"  最適化試行回数: {N_TRIALS} trials/fold")
print(f"  ホライズン: {HORIZON_MONTHS}ヶ月")
print(f"  期間: {START_DATE} ～ {END_DATE}")
print(f"  評価終了年ホールドアウト: {HOLDOUT_EVAL_YEAR}")
print(f"  推定fold数: {ESTIMATED_FOLDS}個")
print()

print("【診断結果（前回）】")
print(f"  1 trialの実行時間: {TRIAL_TIME_SECONDS:.1f}秒（{TRIAL_TIME_MINUTES:.1f}分）")
print()

# 各foldの実行時間見積もり
print("【各foldの実行時間見積もり】")
print(f"  最適化時間: {N_TRIALS} trials × {TRIAL_TIME_MINUTES:.1f}分 = {N_TRIALS * TRIAL_TIME_MINUTES:.1f}分")
print(f"  Test期間バックテスト: 約5-10分（12ポートフォリオ）")
print(f"  合計/fold: 約{N_TRIALS * TRIAL_TIME_MINUTES + 7.5:.1f}分（約{(N_TRIALS * TRIAL_TIME_MINUTES + 7.5) / 60:.1f}時間）")
print()

# 全体の実行時間見積もり
total_time_minutes = ESTIMATED_FOLDS * (N_TRIALS * TRIAL_TIME_MINUTES + 7.5)
total_time_hours = total_time_minutes / 60

print("【全体の実行時間見積もり】")
print(f"  {ESTIMATED_FOLDS} folds × {N_TRIALS * TRIAL_TIME_MINUTES + 7.5:.1f}分/fold")
print(f"  = {total_time_minutes:.1f}分")
print(f"  = {total_time_hours:.1f}時間")
print()

# CPU利用率が3%の場合の補正
# CPU利用率が低い = 逐次実行でCPUが十分に使われていない（正常）
# これはn_jobs_optuna=1のためで、実行時間への影響は小さい
print("【CPU利用率について】")
print(f"  CPU利用率: 約3%")
print(f"  理由: n_jobs_optuna=1（逐次実行）のため、CPUが十分に使われていない")
print(f"  影響: 実行時間への影響は小さい（正常な動作）")
print()

# バッファ込みの見積もり
buffer_hours = total_time_hours * 1.2  # 20%のバッファ

print("【バッファ込みの見積もり】")
print(f"  見積もり: {total_time_hours:.1f}時間")
print(f"  バッファ込み: {buffer_hours:.1f}時間（約{int(buffer_hours)}時間{int((buffer_hours - int(buffer_hours)) * 60)}分）")
print()

print("【注意事項】")
print("  - 実際のfold数は実行時に確定します")
print("  - データ範囲によってfold数が変わる可能性があります")
print("  - 各foldのtrain期間が異なるため、実行時間が変動する可能性があります")
print()










