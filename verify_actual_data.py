#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
実際のデータで計算ロジックを検証
特に、2022-2023年のTOPIXの動きと個別ポートフォリオのパフォーマンスを確認
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
from omanta_3rd.infra.db import connect_db
from omanta_3rd.ingest.indices import TOPIX_CODE

# 結果ファイルを読み込む
with open('walk_forward_longterm_12M_roll_evalYear2025.json', 'r', encoding='utf-8') as f:
    wf_result = json.load(f)

print("=" * 80)
print("実際のデータで計算ロジックを検証")
print("=" * 80)

# Fold 2（2022年）とFold 3（2023年）の詳細を確認
problematic_folds = [2, 3]

with connect_db() as conn:
    for fold_num in problematic_folds:
        fold_data = next((f for f in wf_result['fold_results'] if f['fold'] == fold_num), None)
        if not fold_data:
            continue
        
        print(f"\n{'='*80}")
        print(f"Fold {fold_num} 実際のデータ検証")
        print(f"{'='*80}")
        
        test_dates = fold_data['test_dates']
        print(f"Test期間: {fold_data['test_start']} ～ {fold_data['test_end']}")
        print(f"リバランス日数: {len(test_dates)}")
        
        # 最初の3つのリバランス日で詳細を確認
        print(f"\n最初の3つのリバランス日の詳細:")
        
        for i, rebalance_date in enumerate(test_dates[:3], 1):
            # 評価日を計算
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_dt = rebalance_dt + relativedelta(months=12)
            eval_date = eval_dt.strftime("%Y-%m-%d")
            
            print(f"\n  [{i}] リバランス日: {rebalance_date}")
            print(f"      評価日（リバランス日+12M）: {eval_date}")
            
            # TOPIXの価格を取得
            # 購入日（リバランス日の翌営業日）
            next_trading_day_df = pd.read_sql_query(
                """
                SELECT MIN(date) as next_date
                FROM prices_daily
                WHERE date > ?
                  AND (open IS NOT NULL OR close IS NOT NULL)
                ORDER BY date
                LIMIT 1
                """,
                conn,
                params=(rebalance_date,),
            )
            
            if not next_trading_day_df.empty:
                next_trading_day = str(next_trading_day_df['next_date'].iloc[0])
                
                # TOPIXの購入価格（始値）
                topix_buy_df = pd.read_sql_query(
                    """
                    SELECT open, close
                    FROM index_daily
                    WHERE index_code = ? AND date <= ?
                    ORDER BY date DESC
                    LIMIT 1
                    """,
                    conn,
                    params=(TOPIX_CODE, next_trading_day),
                )
                
                # TOPIXの評価日価格（終値）
                topix_sell_df = pd.read_sql_query(
                    """
                    SELECT close
                    FROM index_daily
                    WHERE index_code = ? AND date <= ?
                    ORDER BY date DESC
                    LIMIT 1
                    """,
                    conn,
                    params=(TOPIX_CODE, eval_date),
                )
                
                if not topix_buy_df.empty and not topix_sell_df.empty:
                    topix_buy_price = topix_buy_df['open'].iloc[0]
                    if pd.isna(topix_buy_price):
                        topix_buy_price = topix_buy_df['close'].iloc[0]
                    topix_sell_price = topix_sell_df['close'].iloc[0]
                    
                    if topix_buy_price and topix_sell_price and topix_buy_price > 0:
                        topix_return = (topix_sell_price - topix_buy_price) / topix_buy_price * 100
                        print(f"      TOPIX購入価格（{next_trading_day}始値）: {topix_buy_price:.2f}")
                        print(f"      TOPIX評価価格（{eval_date}終値）: {topix_sell_price:.2f}")
                        print(f"      TOPIXリターン: {topix_return:.2f}%")
                    else:
                        print(f"      ⚠️  TOPIX価格データが取得できませんでした")
                else:
                    print(f"      ⚠️  TOPIX価格データが見つかりませんでした")
            else:
                print(f"      ⚠️  翌営業日が見つかりませんでした")
        
        # 2022年と2023年のTOPIXの年間リターンを確認
        print(f"\n【{fold_data['test_start'][:4]}年のTOPIX年間リターン】")
        
        # 年初と年末のTOPIX価格を取得
        year_start = fold_data['test_start'][:4] + "-01-01"
        year_end = fold_data['test_end']
        
        # 年初のTOPIX価格
        topix_start_df = pd.read_sql_query(
            """
            SELECT close
            FROM index_daily
            WHERE index_code = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
            LIMIT 1
            """,
            conn,
            params=(TOPIX_CODE, year_start, year_end),
        )
        
        # 年末のTOPIX価格
        topix_end_df = pd.read_sql_query(
            """
            SELECT close
            FROM index_daily
            WHERE index_code = ? AND date >= ? AND date <= ?
            ORDER BY date DESC
            LIMIT 1
            """,
            conn,
            params=(TOPIX_CODE, year_start, year_end),
        )
        
        if not topix_start_df.empty and not topix_end_df.empty:
            topix_start_price = topix_start_df['close'].iloc[0]
            topix_end_price = topix_end_df['close'].iloc[0]
            
            if topix_start_price and topix_end_price and topix_start_price > 0:
                topix_year_return = (topix_end_price - topix_start_price) / topix_start_price * 100
                print(f"  年初（{year_start}）: {topix_start_price:.2f}")
                print(f"  年末（{year_end}）: {topix_end_price:.2f}")
                print(f"  年間リターン: {topix_year_return:.2f}%")
                
                if topix_year_return < 0:
                    print(f"  ⚠️  {fold_data['test_start'][:4]}年はTOPIXが下落した年です")
                else:
                    print(f"  ✓ {fold_data['test_start'][:4]}年はTOPIXが上昇した年です")

print("\n" + "=" * 80)
print("検証完了")
print("=" * 80)


