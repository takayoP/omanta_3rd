#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
strategy_params_monthly_rebalanceテーブルのパラメータを表示するスクリプト
"""

from omanta_3rd.infra.db import connect_db

def main():
    with connect_db() as conn:
        cursor = conn.execute("""
            SELECT 
                trial_number, ranking, recommendation_text,
                w_quality, w_growth, w_record_high, w_size, w_value,
                w_forward_per, roe_min, bb_weight, liquidity_quantile_cut,
                rsi_base, rsi_max, bb_z_base, bb_z_max,
                json_file_path
            FROM strategy_params_monthly_rebalance
            ORDER BY ranking, trial_number
        """)
        
        print("=" * 80)
        print("月次リバランス型パラメータ一覧")
        print("=" * 80)
        
        for row in cursor.fetchall():
            (trial_number, ranking, recommendation_text,
             w_quality, w_growth, w_record_high, w_size, w_value,
             w_forward_per, roe_min, bb_weight, liquidity_quantile_cut,
             rsi_base, rsi_max, bb_z_base, bb_z_max,
             json_file_path) = row
            
            print(f"\n【Trial #{trial_number}】")
            print(f"  ランキング: {ranking}")
            print(f"  推奨: {recommendation_text}")
            print(f"  主要パラメータ:")
            print(f"    RSI: base={rsi_base:.2f}, max={rsi_max:.2f} ({'順張り' if rsi_max > rsi_base else '逆張り'})")
            print(f"    BB Z-score: base={bb_z_base:.2f}, max={bb_z_max:.2f} ({'順張り' if bb_z_max > bb_z_base else '逆張り'})")
            print(f"    重み: Quality={w_quality:.3f}, Value={w_value:.3f}, Growth={w_growth:.3f}, Size={w_size:.3f}")
            print(f"    BB Weight: {bb_weight:.3f}")
            if json_file_path:
                print(f"  JSONファイル: {json_file_path}")
            else:
                print(f"  JSONファイル: 未設定")
            print("-" * 80)

if __name__ == "__main__":
    main()









