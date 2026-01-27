#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
旧best paramsを今の等ウェイト実装で再評価するスクリプト

同じtrain_dates（36本）に対して：
1. 現在のbest params（train=1.44%）
2. 以前のbest params（train=13.49%だったやつ）

を、今のコード（等ウェイト統一後）で固定評価して、trainのmean_annual_excess_return_pctを出す。
"""

import json
from pathlib import Path
from dataclasses import dataclass, replace, fields
from datetime import datetime

from omanta_3rd.jobs.longterm_run import StrategyParams
from omanta_3rd.jobs.optimize import EntryScoreParams
from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.optimize_longterm import calculate_longterm_performance
from omanta_3rd.backtest.feature_cache import FeatureCache

# 最適化結果JSONを読み込む
result_file_20260112 = Path("optimization_result_operational_24M_lambda0.00_20260112.json")
result_file_20260111 = Path("optimization_result_operational_24M_lambda0.00_20260111.json")

print("=" * 80)
print("旧best paramsを今の等ウェイト実装で再評価")
print("=" * 80)
print()

# 現在の結果からtrain_datesを取得
if not result_file_20260112.exists():
    print("❌ 現在の結果ファイルが見つかりません")
    exit(1)

with open(result_file_20260112, "r", encoding="utf-8") as f:
    data_current = json.load(f)

train_dates = data_current.get("train_dates", [])
if not train_dates:
    print("❌ train_datesが見つかりません")
    exit(1)

print(f"train_dates: {len(train_dates)}件")
print(f"  最初: {train_dates[0]}")
print(f"  最後: {train_dates[-1]}")
print()

# as_of_dateとtrain_end_dateを決定
# train_dates_last = 2020-12-30の場合、eval_end = 2022-12-30
# as_of_dateは2022-12-30より後であればOK（train_end_dateを使用）
train_end_date = "2022-12-31"  # 固定
as_of_date = train_end_date  # train評価ではtrain_end_dateを使用

print(f"as_of_date: {as_of_date}")
print(f"train_end_date: {train_end_date}")
print()

# 特徴量キャッシュを構築
print("特徴量キャッシュを構築中...")
try:
    feature_cache = FeatureCache(cache_dir="cache/features")
    # Windowsでの並列処理の問題を回避するため、n_jobs=1で実行
    features_dict, prices_dict = feature_cache.warm(
        train_dates,
        n_jobs=1  # WindowsでのBrokenProcessPoolエラーを回避
    )
    print(f"特徴量: {len(features_dict)}日分、価格データ: {len(prices_dict)}日分")
    print()
except Exception as e:
    print(f"❌ 特徴量キャッシュの構築に失敗しました: {e}")
    print("   既存のキャッシュを使用するか、n_jobs=1で再試行してください")
    import traceback
    traceback.print_exc()
    exit(1)

# 評価関数
def evaluate_params(params_data, label):
    """指定されたパラメータでtrain期間を評価"""
    print(f"【{label}】")
    
    # StrategyParamsを構築
    normalized_params = params_data.get("normalized_params", {})
    default_params = StrategyParams()
    strategy_params = replace(
        default_params,
        target_min=12,
        target_max=12,
        w_quality=normalized_params.get("w_quality", 0.0),
        w_value=normalized_params.get("w_value", 0.0),
        w_growth=normalized_params.get("w_growth", 0.0),
        w_record_high=normalized_params.get("w_record_high", 0.0),
        w_size=normalized_params.get("w_size", 0.0),
        w_forward_per=normalized_params.get("w_forward_per", 0.0),
        w_pbr=normalized_params.get("w_pbr", 0.0),
        roe_min=normalized_params.get("roe_min", 0.0),
        liquidity_quantile_cut=normalized_params.get("liquidity_quantile_cut", 0.0),
    )
    
    # EntryScoreParamsを構築
    entry_params = EntryScoreParams(
        rsi_base=normalized_params.get("rsi_base", 0.0),
        rsi_max=normalized_params.get("rsi_max", 0.0),
        bb_z_base=normalized_params.get("bb_z_base", 0.0),
        bb_z_max=normalized_params.get("bb_z_max", 0.0),
        bb_weight=normalized_params.get("bb_weight", 0.0),
        rsi_weight=normalized_params.get("rsi_weight", 0.0),
        rsi_min_width=normalized_params.get("rsi_min_width", 10.0),
        bb_z_min_width=normalized_params.get("bb_z_min_width", 0.5),
    )
    
    # パフォーマンスを計算
    # Windowsでの並列処理の問題を回避するため、n_jobs=1で実行
    perf = calculate_longterm_performance(
        train_dates,
        strategy_params,
        entry_params,
        cost_bps=0.0,
        n_jobs=1,  # WindowsでのBrokenProcessPoolエラーを回避
        features_dict=features_dict,
        prices_dict=prices_dict,
        horizon_months=24,
        require_full_horizon=True,
        as_of_date=as_of_date,
    )
    
    print(f"  総ポートフォリオ数: {perf.get('num_portfolios', 'N/A')}")
    print(f"  評価成功: {perf.get('num_performances', 'N/A')}")
    print(f"  mean_annual_excess_return_pct: {perf.get('mean_annual_excess_return_pct', 'N/A'):.4f}%")
    print(f"  n_periods: {perf.get('n_periods', 'N/A')}")
    print()
    
    return perf

# 現在のbest paramsで評価
if result_file_20260112.exists():
    with open(result_file_20260112, "r", encoding="utf-8") as f:
        data_current = json.load(f)
    perf_current = evaluate_params(data_current, "現在のbest params（train=1.44%だったやつ）")
else:
    print("❌ 現在の結果ファイルが見つかりません")
    exit(1)

# 以前のbest paramsで評価
if result_file_20260111.exists():
    with open(result_file_20260111, "r", encoding="utf-8") as f:
        data_previous = json.load(f)
    perf_previous = evaluate_params(data_previous, "以前のbest params（train=13.49%だったやつ）")
else:
    print("⚠️  以前の結果ファイルが見つかりません。スキップします。")
    perf_previous = None

# 結果の比較
print("=" * 80)
print("【結果の比較】")
print("=" * 80)
print()
print("現在のbest params（等ウェイト実装で再評価）:")
print(f"  mean_annual_excess_return_pct: {perf_current.get('mean_annual_excess_return_pct', 'N/A'):.4f}%")
print(f"  n_periods: {perf_current.get('n_periods', 'N/A')}")
print()

if perf_previous:
    print("以前のbest params（等ウェイト実装で再評価）:")
    print(f"  mean_annual_excess_return_pct: {perf_previous.get('mean_annual_excess_return_pct', 'N/A'):.4f}%")
    print(f"  n_periods: {perf_previous.get('n_periods', 'N/A')}")
    print()
    
    print("【解釈】")
    prev_excess = perf_previous.get('mean_annual_excess_return_pct', 0.0)
    if prev_excess > 10.0:
        print("  → 以前のparamsを等ウェイトで再評価しても10%超が再現")
        print("  → 現optimizerがその近辺を見つけられていない可能性")
        print("  → direction/探索空間/サンプリング/制約/バグを疑うべき")
    elif prev_excess < 3.0:
        print("  → 以前のparamsを等ウェイトで再評価しても1〜2%程度")
        print("  → 13.49%は「別戦略/別算出」の数字だった可能性が高い")
        print("  → 今の1.44%は「現実」")
    else:
        print(f"  → 以前のparamsを等ウェイトで再評価: {prev_excess:.2f}%")
        print("  → 中間的な結果。さらなる調査が必要")

print()

