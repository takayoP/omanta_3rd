#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Walk-Forward Analysisの計算ロジックを詳細に検証
特に、年率化と超過リターンの計算を確認
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta

# 結果ファイルを読み込む
with open('walk_forward_longterm_12M_roll_evalYear2025.json', 'r', encoding='utf-8') as f:
    wf_result = json.load(f)

print("=" * 80)
print("Walk-Forward Analysis 計算ロジック詳細検証")
print("=" * 80)

# 各foldの計算ロジックを検証
for fold_data in wf_result['fold_results']:
    fold_num = fold_data['fold']
    fold_label = fold_data['fold_label']
    
    print(f"\n{'='*80}")
    print(f"Fold {fold_num} ({fold_label})")
    print(f"{'='*80}")
    
    test_perf = fold_data['test_performance']
    ann_excess_mean = test_perf['ann_excess_mean']
    ann_excess_median = test_perf['ann_excess_median']
    win_rate = test_perf['win_rate']
    n_portfolios = test_perf['n_portfolios']
    
    print(f"年率超過リターン（平均）: {ann_excess_mean:.2f}%")
    print(f"年率超過リターン（中央値）: {ann_excess_median:.2f}%")
    print(f"勝率: {win_rate:.1%}")
    print(f"ポートフォリオ数: {n_portfolios}")
    
    # 計算ロジックの検証
    print(f"\n【計算ロジックの検証】")
    
    # 1. 評価日の計算方法を確認
    test_dates = fold_data['test_dates']
    print(f"Test期間のリバランス日数: {len(test_dates)}")
    
    # 最初と最後のリバランス日で評価日を計算
    first_rebalance = test_dates[0]
    last_rebalance = test_dates[-1]
    
    first_rebalance_dt = datetime.strptime(first_rebalance, "%Y-%m-%d")
    last_rebalance_dt = datetime.strptime(last_rebalance, "%Y-%m-%d")
    
    first_eval_dt = first_rebalance_dt + relativedelta(months=12)
    last_eval_dt = last_rebalance_dt + relativedelta(months=12)
    
    print(f"最初のリバランス日: {first_rebalance}")
    print(f"最初の評価日（リバランス日+12M）: {first_eval_dt.strftime('%Y-%m-%d')}")
    print(f"最後のリバランス日: {last_rebalance}")
    print(f"最後の評価日（リバランス日+12M）: {last_eval_dt.strftime('%Y-%m-%d')}")
    
    # 2. 年率化の計算方法を確認
    print(f"\n【年率化の計算方法】")
    print(f"固定ホライズン: 12ヶ月 = 1.0年")
    print(f"年率化式: (1 + 累積リターン) ^ (1 / 保有年数) - 1")
    
    # サンプル計算
    sample_returns = [-20.0, -10.0, 0.0, 10.0, 20.0]  # 累積リターン（%）
    holding_years = 1.0  # 12ヶ月 = 1.0年
    
    print(f"\nサンプル計算（保有期間: {holding_years}年）:")
    for cum_return in sample_returns:
        return_factor = 1 + cum_return / 100
        if return_factor > 0:
            annual_return = (return_factor ** (1 / holding_years) - 1) * 100
            print(f"  累積リターン {cum_return:6.1f}% → 年率リターン {annual_return:6.1f}%")
        else:
            print(f"  累積リターン {cum_return:6.1f}% → 年率化不可（-100%未満）")
    
    # 3. 超過リターンの年率化を確認
    print(f"\n【超過リターンの年率化】")
    print(f"超過リターンも同様に年率化される")
    print(f"年率超過リターン = (1 + 累積超過リターン) ^ (1 / 保有年数) - 1")
    
    sample_excess_returns = [-15.0, -5.0, 0.0, 5.0, 15.0]  # 累積超過リターン（%）
    
    print(f"\nサンプル計算（保有期間: {holding_years}年）:")
    for cum_excess in sample_excess_returns:
        excess_factor = 1 + cum_excess / 100
        if excess_factor > 0:
            annual_excess = (excess_factor ** (1 / holding_years) - 1) * 100
            print(f"  累積超過リターン {cum_excess:6.1f}% → 年率超過リターン {annual_excess:6.1f}%")
        else:
            print(f"  累積超過リターン {cum_excess:6.1f}% → 年率化不可（-100%未満）")
    
    # 4. 勝率の計算を確認
    print(f"\n【勝率の計算】")
    print(f"勝率 = 年率超過リターン > 0 のポートフォリオ数 / 全ポートフォリオ数")
    print(f"実際の勝率: {win_rate:.1%}")
    print(f"ポートフォリオ数: {n_portfolios}")
    
    # 5. 平均と中央値の関係を確認
    print(f"\n【平均と中央値の関係】")
    print(f"平均年率超過リターン: {ann_excess_mean:.2f}%")
    print(f"中央値年率超過リターン: {ann_excess_median:.2f}%")
    
    if ann_excess_mean < ann_excess_median:
        print(f"⚠️  平均 < 中央値 → 負の外れ値（大きな損失）が存在する可能性")
    elif ann_excess_mean > ann_excess_median:
        print(f"✓ 平均 > 中央値 → 正の外れ値（大きな利益）が存在する可能性")
    else:
        print(f"✓ 平均 ≈ 中央値 → 分布が対称的")

print("\n" + "=" * 80)
print("検証完了")
print("=" * 80)

# 追加: 計算ロジックの数式を確認
print("\n" + "=" * 80)
print("計算ロジックの数式確認")
print("=" * 80)

print("""
【固定ホライズン（12M）の計算ロジック】

1. 評価日の計算:
   評価日 = リバランス日 + 12ヶ月

2. 累積リターンの計算:
   累積リターン = (評価日価格 - 購入価格) / 購入価格 × 100
   
3. 年率リターンの計算:
   年率リターン = (1 + 累積リターン/100) ^ (1 / 保有年数) - 1
   保有年数 = 12ヶ月 / 12 = 1.0年
   
4. 累積超過リターンの計算:
   累積超過リターン = ポートフォリオリターン - TOPIXリターン
   
5. 年率超過リターンの計算:
   年率超過リターン = (1 + 累積超過リターン/100) ^ (1 / 保有年数) - 1
   
6. 勝率の計算:
   勝率 = 年率超過リターン > 0 のポートフォリオ数 / 全ポートフォリオ数

【注意点】
- 固定ホライズン（12M）の場合、保有年数は常に1.0年
- 年率化は単純に累積リターンを1年で割るのではなく、複利計算を使用
- 例: 累積リターン -20% → 年率リターン = (1 - 0.20)^1 - 1 = -20%
- 例: 累積リターン +20% → 年率リターン = (1 + 0.20)^1 - 1 = +20%
""")


