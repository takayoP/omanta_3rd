#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
相互補完機能による改善度を測定
補完前と補完後のデータ埋まり率を比較
"""

import sys
from pathlib import Path
import pandas as pd
import sqlite3

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _load_latest_fy

asof = "2025-12-19"

print("=== 相互補完機能による改善度の測定 ===\n")
print(f"基準日: {asof}\n")

with connect_db(read_only=True) as conn:
    # 補完前の状態を確認（開示日が最新のFYデータのみ、相互補完なし）
    print("【補完前】開示日が最新のFYデータのみ（相互補完なし）:\n")
    
    before_df = pd.read_sql_query("""
        SELECT disclosed_date, code, current_period_end,
               operating_profit, forecast_operating_profit,
               profit, forecast_profit, forecast_eps, eps
        FROM fins_statements
        WHERE disclosed_date <= ?
          AND type_of_current_period = 'FY'
          AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL
               OR forecast_operating_profit IS NOT NULL OR forecast_profit IS NOT NULL OR forecast_eps IS NOT NULL)
    """, conn, params=(asof,))
    
    if not before_df.empty:
        before_df["disclosed_date"] = pd.to_datetime(before_df["disclosed_date"], errors="coerce")
        before_df["current_period_end"] = pd.to_datetime(before_df["current_period_end"], errors="coerce")
        
        # 開示日が最新のものを選ぶ（相互補完なし）
        before_df = before_df.sort_values(["code", "disclosed_date"])
        before_latest = before_df.groupby("code", as_index=False).tail(1).copy()
        
        before_op = before_latest["operating_profit"].notna().sum()
        before_forecast_op = before_latest["forecast_operating_profit"].notna().sum()
        before_profit = before_latest["profit"].notna().sum()
        before_forecast_profit = before_latest["forecast_profit"].notna().sum()
        before_forecast_eps = before_latest["forecast_eps"].notna().sum()
        before_total = len(before_latest)
        
        print(f"  総銘柄数: {before_total}")
        print(f"  operating_profit: {before_op}/{before_total} ({before_op/before_total*100:.1f}%)")
        print(f"  forecast_operating_profit: {before_forecast_op}/{before_total} ({before_forecast_op/before_total*100:.1f}%)")
        print(f"  profit: {before_profit}/{before_total} ({before_profit/before_total*100:.1f}%)")
        print(f"  forecast_profit: {before_forecast_profit}/{before_total} ({before_forecast_profit/before_total*100:.1f}%)")
        print(f"  forecast_eps: {before_forecast_eps}/{before_total} ({before_forecast_eps/before_total*100:.1f}%)")
        
        # 相互補完可能なケースをカウント
        # operating_profitが欠損だが、同じcurrent_period_endにforecast_operating_profitがあるケース
        can_complement_op = 0
        can_complement_profit = 0
        can_complement_eps = 0
        
        for code in before_latest["code"].unique():
            code_data = before_df[before_df["code"] == code]
            latest_row = before_latest[before_latest["code"] == code]
            if latest_row.empty:
                continue
            
            latest_period = latest_row.iloc[0]["current_period_end"]
            same_period_data = code_data[code_data["current_period_end"] == latest_period]
            
            latest_op = latest_row.iloc[0]["operating_profit"]
            latest_forecast_op = latest_row.iloc[0]["forecast_operating_profit"]
            latest_profit = latest_row.iloc[0]["profit"]
            latest_forecast_profit = latest_row.iloc[0]["forecast_profit"]
            latest_forecast_eps = latest_row.iloc[0]["forecast_eps"]
            
            # 同じcurrent_period_endに補完可能なデータがあるか
            if pd.isna(latest_op) and same_period_data["forecast_operating_profit"].notna().any():
                can_complement_op += 1
            if pd.isna(latest_forecast_op) and same_period_data["operating_profit"].notna().any():
                can_complement_op += 1
            
            if pd.isna(latest_profit) and same_period_data["forecast_profit"].notna().any():
                can_complement_profit += 1
            if pd.isna(latest_forecast_profit) and same_period_data["profit"].notna().any():
                can_complement_profit += 1
            
            if pd.isna(latest_forecast_eps) and same_period_data["eps"].notna().any():
                can_complement_eps += 1
        
        print(f"\n  相互補完可能なケース:")
        print(f"    operating_profit/forecast_operating_profit: {can_complement_op}件")
        print(f"    profit/forecast_profit: {can_complement_profit}件")
        print(f"    forecast_eps: {can_complement_eps}件")
    
    print("\n" + "="*60)
    
    # 補完後の状態を確認（_load_latest_fyを使用）
    print("【補完後】_load_latest_fyで相互補完を実施後:\n")
    
    after_latest = _load_latest_fy(conn, asof)
    
    if not after_latest.empty:
        after_op = after_latest["operating_profit"].notna().sum()
        after_forecast_op = after_latest["forecast_operating_profit"].notna().sum()
        after_profit = after_latest["profit"].notna().sum()
        after_forecast_profit = after_latest["forecast_profit"].notna().sum()
        after_forecast_eps = after_latest["forecast_eps"].notna().sum()
        after_total = len(after_latest)
        
        print(f"  総銘柄数: {after_total}")
        print(f"  operating_profit: {after_op}/{after_total} ({after_op/after_total*100:.1f}%)")
        print(f"  forecast_operating_profit: {after_forecast_op}/{after_total} ({after_forecast_op/after_total*100:.1f}%)")
        print(f"  profit: {after_profit}/{after_total} ({after_profit/after_total*100:.1f}%)")
        print(f"  forecast_profit: {after_forecast_profit}/{after_total} ({after_forecast_profit/after_total*100:.1f}%)")
        print(f"  forecast_eps: {after_forecast_eps}/{after_total} ({after_forecast_eps/after_total*100:.1f}%)")
    
    print("\n" + "="*60)
    print("【改善度】\n")
    
    if not before_latest.empty and not after_latest.empty:
        # 共通の銘柄で比較
        common_codes = set(before_latest["code"]) & set(after_latest["code"])
        before_common = before_latest[before_latest["code"].isin(common_codes)]
        after_common = after_latest[after_latest["code"].isin(common_codes)]
        
        print(f"比較対象銘柄数: {len(common_codes)}\n")
        
        # operating_profit
        before_op_common = before_common["operating_profit"].notna().sum()
        after_op_common = after_common["operating_profit"].notna().sum()
        op_improvement = after_op_common - before_op_common
        op_improvement_pct = (op_improvement / len(common_codes)) * 100.0 if len(common_codes) > 0 else 0.0
        print(f"operating_profit:")
        print(f"  補完前: {before_op_common}/{len(common_codes)} ({before_op_common/len(common_codes)*100:.1f}%)")
        print(f"  補完後: {after_op_common}/{len(common_codes)} ({after_op_common/len(common_codes)*100:.1f}%)")
        print(f"  改善: +{op_improvement}件 (+{op_improvement_pct:.1f}ポイント)\n")
        
        # forecast_operating_profit
        before_forecast_op_common = before_common["forecast_operating_profit"].notna().sum()
        after_forecast_op_common = after_common["forecast_operating_profit"].notna().sum()
        forecast_op_improvement = after_forecast_op_common - before_forecast_op_common
        forecast_op_improvement_pct = (forecast_op_improvement / len(common_codes)) * 100.0 if len(common_codes) > 0 else 0.0
        print(f"forecast_operating_profit:")
        print(f"  補完前: {before_forecast_op_common}/{len(common_codes)} ({before_forecast_op_common/len(common_codes)*100:.1f}%)")
        print(f"  補完後: {after_forecast_op_common}/{len(common_codes)} ({after_forecast_op_common/len(common_codes)*100:.1f}%)")
        print(f"  改善: +{forecast_op_improvement}件 (+{forecast_op_improvement_pct:.1f}ポイント)\n")
        
        # profit
        before_profit_common = before_common["profit"].notna().sum()
        after_profit_common = after_common["profit"].notna().sum()
        profit_improvement = after_profit_common - before_profit_common
        profit_improvement_pct = (profit_improvement / len(common_codes)) * 100.0 if len(common_codes) > 0 else 0.0
        print(f"profit:")
        print(f"  補完前: {before_profit_common}/{len(common_codes)} ({before_profit_common/len(common_codes)*100:.1f}%)")
        print(f"  補完後: {after_profit_common}/{len(common_codes)} ({after_profit_common/len(common_codes)*100:.1f}%)")
        print(f"  改善: +{profit_improvement}件 (+{profit_improvement_pct:.1f}ポイント)\n")
        
        # forecast_profit
        before_forecast_profit_common = before_common["forecast_profit"].notna().sum()
        after_forecast_profit_common = after_common["forecast_profit"].notna().sum()
        forecast_profit_improvement = after_forecast_profit_common - before_forecast_profit_common
        forecast_profit_improvement_pct = (forecast_profit_improvement / len(common_codes)) * 100.0 if len(common_codes) > 0 else 0.0
        print(f"forecast_profit:")
        print(f"  補完前: {before_forecast_profit_common}/{len(common_codes)} ({before_forecast_profit_common/len(common_codes)*100:.1f}%)")
        print(f"  補完後: {after_forecast_profit_common}/{len(common_codes)} ({after_forecast_profit_common/len(common_codes)*100:.1f}%)")
        print(f"  改善: +{forecast_profit_improvement}件 (+{forecast_profit_improvement_pct:.1f}ポイント)\n")
        
        # forecast_eps
        before_forecast_eps_common = before_common["forecast_eps"].notna().sum()
        after_forecast_eps_common = after_common["forecast_eps"].notna().sum()
        forecast_eps_improvement = after_forecast_eps_common - before_forecast_eps_common
        forecast_eps_improvement_pct = (forecast_eps_improvement / len(common_codes)) * 100.0 if len(common_codes) > 0 else 0.0
        print(f"forecast_eps:")
        print(f"  補完前: {before_forecast_eps_common}/{len(common_codes)} ({before_forecast_eps_common/len(common_codes)*100:.1f}%)")
        print(f"  補完後: {after_forecast_eps_common}/{len(common_codes)} ({after_forecast_eps_common/len(common_codes)*100:.1f}%)")
        print(f"  改善: +{forecast_eps_improvement}件 (+{forecast_eps_improvement_pct:.1f}ポイント)\n")
        
        # 総合改善度
        total_improvements = (
            op_improvement + forecast_op_improvement +
            profit_improvement + forecast_profit_improvement +
            forecast_eps_improvement
        )
        total_possible = len(common_codes) * 5  # 5つの項目
        total_improvement_pct = (total_improvements / total_possible) * 100.0 if total_possible > 0 else 0.0
        print(f"【総合】")
        print(f"  総改善件数: {total_improvements}件（5項目×{len(common_codes)}銘柄中）")
        print(f"  総合改善率: {total_improvement_pct:.2f}%")

print("\n" + "="*60)
print("測定完了")
