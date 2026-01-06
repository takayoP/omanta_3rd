#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DBからパラメータを表示するスクリプト

保存されたパラメータをわかりやすく表示します。
"""

import json
from omanta_3rd.infra.db import connect_db

def view_params():
    """DBからパラメータを表示"""
    with connect_db() as conn:
        cursor = conn.execute("""
            SELECT 
                param_id, horizon_months, strategy_type, portfolio_type, strategy_mode,
                source_fold, source_test_period, description, recommended_for,
                w_quality, w_growth, w_record_high, w_size, w_value,
                w_forward_per, roe_min, bb_weight, liquidity_quantile_cut,
                rsi_base, rsi_max, bb_z_base, bb_z_max,
                rsi_min_width, bb_z_min_width,
                metadata_json, performance_json, cross_validation_json,
                json_file_path,
                created_at, updated_at, is_active
            FROM strategy_params
            WHERE is_active = 1
            ORDER BY 
                CASE strategy_type 
                    WHEN 'operational' THEN 1 
                    ELSE 2 
                END,
                horizon_months,
                param_id
        """)
        
        rows = cursor.fetchall()
        
        if not rows:
            print("保存されたパラメータがありません。")
            return
        
        print("=" * 80)
        print("保存されたパラメータ一覧")
        print("=" * 80)
        print()
        
        for row in rows:
            (param_id, horizon, stype, ptype, mode, source_fold, source_test_period,
             desc, rec, w_quality, w_growth, w_record_high, w_size, w_value,
             w_forward_per, roe_min, bb_weight, liquidity_quantile_cut,
             rsi_base, rsi_max, bb_z_base, bb_z_max,
             rsi_min_width, bb_z_min_width,
             metadata_json, performance_json, cross_validation_json,
             json_file_path,
             created_at, updated_at, is_active) = row
            
            print(f"【{param_id}】")
            print(f"  ホライズン: {horizon}M")
            print(f"  タイプ: {stype} ({'運用用' if stype == 'operational' else '研究用'})")
            ptype_label = "長期保有型" if ptype == "longterm" else "月次リバランス型"
            print(f"  ポートフォリオタイプ: {ptype_label}")
            print(f"  モード: {mode} ({'順張り' if mode == 'momentum' else '逆張り' if mode == 'reversal' else '混合'})")
            print(f"  元のfold: {source_fold}")
            print(f"  元のテスト期間: {source_test_period}")
            print(f"  推奨用途: {rec}")
            print()
            
            if desc:
                print(f"  説明: {desc}")
                print()
            
            # パフォーマンス情報
            if performance_json:
                perf = json.loads(performance_json)
                print("  元のパフォーマンス:")
                if "ann_excess_mean" in perf:
                    print(f"    年率超過リターン: {perf['ann_excess_mean']:.2f}%")
                if "win_rate" in perf:
                    print(f"    勝率: {perf['win_rate']:.1%}")
                if "n_portfolios" in perf:
                    print(f"    ポートフォリオ数: {perf['n_portfolios']}")
                print()
            
            # 横持ち評価結果
            if cross_validation_json:
                cv = json.loads(cross_validation_json)
                if cv:
                    print("  横持ち評価結果:")
                    for year, result in cv.items():
                        if isinstance(result, dict) and "ann_excess_mean" in result:
                            print(f"    {year}: {result['ann_excess_mean']:.2f}% "
                                  f"(勝率: {result.get('win_rate', 0):.1%})")
                    print()
            
            # 主要パラメータ
            print("  主要パラメータ:")
            print(f"    RSI: base={rsi_base:.2f}, max={rsi_max:.2f} "
                  f"({'順張り' if rsi_max > rsi_base else '逆張り'})")
            print(f"    BB Z-score: base={bb_z_base:.2f}, max={bb_z_max:.2f} "
                  f"({'順張り' if bb_z_max > bb_z_base else '逆張り'})")
            print(f"    重み: Quality={w_quality:.3f}, Value={w_value:.3f}, "
                  f"Growth={w_growth:.3f}, Size={w_size:.3f}")
            print(f"    BB Weight: {bb_weight:.3f}")
            print()
            
            if json_file_path:
                print(f"  JSONファイル: {json_file_path}")
                print()
            
            print("-" * 80)
            print()

if __name__ == "__main__":
    view_params()

