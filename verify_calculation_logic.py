#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Walk-Forward Analysisの計算ロジックを検証するスクリプト
特に、2022-2023年の結果が悪い理由を調査
"""

import json
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from omanta_3rd.infra.db import connect_db
from omanta_3rd.backtest.performance import calculate_portfolio_performance

# 結果ファイルを読み込む
with open('walk_forward_longterm_12M_roll_evalYear2025.json', 'r', encoding='utf-8') as f:
    wf_result = json.load(f)

print("=" * 80)
print("Walk-Forward Analysis 計算ロジック検証")
print("=" * 80)

# Fold 2（2022年）とFold 3（2023年）の詳細を確認
problematic_folds = [2, 3]

for fold_num in problematic_folds:
    fold_data = next((f for f in wf_result['fold_results'] if f['fold'] == fold_num), None)
    if not fold_data:
        continue
    
    print(f"\n{'='*80}")
    print(f"Fold {fold_num} 詳細分析")
    print(f"{'='*80}")
    print(f"Train期間: {fold_data['train_start']} ～ {fold_data['train_end']}")
    print(f"Test期間: {fold_data['test_start']} ～ {fold_data['test_end']}")
    print(f"年率超過リターン（平均）: {fold_data['test_performance']['ann_excess_mean']:.2f}%")
    print(f"勝率: {fold_data['test_performance']['win_rate']:.1%}")
    
    # 各リバランス日のパフォーマンスを個別に確認
    test_dates = fold_data['test_dates']
    print(f"\n各リバランス日のパフォーマンス:")
    
    with connect_db() as conn:
        for i, rebalance_date in enumerate(test_dates[:3], 1):  # 最初の3つを確認
            # 評価日を計算（リバランス日 + 12ヶ月）
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_dt = rebalance_dt + relativedelta(months=12)
            eval_date = eval_dt.strftime("%Y-%m-%d")
            
            print(f"\n  [{i}] リバランス日: {rebalance_date}")
            print(f"      評価日（リバランス日+12M）: {eval_date}")
            
            # ポートフォリオが存在するか確認
            portfolio = pd.read_sql_query(
                """
                SELECT code, weight
                FROM portfolio_monthly
                WHERE rebalance_date = ?
                """,
                conn,
                params=(rebalance_date,),
            )
            
            if portfolio.empty:
                print(f"      ⚠️  ポートフォリオが見つかりません")
                continue
            
            print(f"      ポートフォリオ銘柄数: {len(portfolio)}")
            
            # パフォーマンスを計算
            perf = calculate_portfolio_performance(rebalance_date, eval_date)
            
            if "error" in perf:
                print(f"      ❌ エラー: {perf['error']}")
                continue
            
            total_return = perf.get('total_return_pct', None)
            topix_comparison = perf.get('topix_comparison', {})
            excess_return = topix_comparison.get('excess_return_pct', None)
            topix_return = topix_comparison.get('topix_return_pct', None)
            
            print(f"      ポートフォリオリターン: {total_return:.2f}%" if total_return else "      ポートフォリオリターン: N/A")
            print(f"      TOPIXリターン: {topix_return:.2f}%" if topix_return else "      TOPIXリターン: N/A")
            print(f"      超過リターン: {excess_return:.2f}%" if excess_return else "      超過リターン: N/A")
            
            # 保有期間を確認
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_dt = datetime.strptime(eval_date, "%Y-%m-%d")
            holding_days = (eval_dt - rebalance_dt).days
            holding_years = holding_days / 365.25
            
            print(f"      保有期間: {holding_days}日（{holding_years:.2f}年）")
            
            # 年率化を確認
            if total_return is not None and holding_years > 0:
                return_factor = 1 + total_return / 100
                if return_factor > 0:
                    annual_return = (return_factor ** (1 / holding_years) - 1) * 100
                    print(f"      年率リターン: {annual_return:.2f}%")
                else:
                    print(f"      ⚠️  累積リターンが-100%未満のため年率化不可")

print("\n" + "=" * 80)
print("検証完了")
print("=" * 80)


