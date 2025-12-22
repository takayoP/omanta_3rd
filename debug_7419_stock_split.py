#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ノジマ7419の株式分割調整のデバッグ
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _get_shares_adjustment_factor

code = "7419"
price_date = "2025-12-19"

print(f"=== ノジマ {code} の株式分割調整デバッグ ===\n")

with connect_db() as conn:
    # 最新期の発行済み株式数と純資産を取得
    latest_data = pd.read_sql_query(
        """
        SELECT shares_outstanding, treasury_shares, equity, current_period_end, disclosed_date
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND shares_outstanding IS NOT NULL
          AND disclosed_date <= ?
        ORDER BY current_period_end DESC, disclosed_date DESC
        LIMIT 1
        """,
        conn,
        params=(code, price_date),
    )
    
    if latest_data.empty:
        print("最新期のデータが見つかりません")
        sys.exit(1)
    
    latest_row = latest_data.iloc[0]
    latest_shares_outstanding = latest_row["shares_outstanding"]
    latest_treasury_shares = latest_row.get("treasury_shares") or 0.0
    latest_equity = latest_row["equity"]
    latest_period_end = latest_row["current_period_end"]
    latest_shares_net = latest_shares_outstanding - latest_treasury_shares
    
    print(f"最新期 ({latest_period_end}):")
    print(f"  発行済み株式数: {latest_shares_outstanding:,.0f}株")
    print(f"  自己株式: {latest_treasury_shares:,.0f}株")
    print(f"  発行済み株式数（自己株式除く）: {latest_shares_net:,.0f}株")
    print(f"  純資産: {latest_equity:,.0f}円")
    print(f"  開示日: {latest_row['disclosed_date']}")
    
    # 全期間のデータを取得して確認
    all_periods = pd.read_sql_query(
        """
        SELECT current_period_end, disclosed_date, shares_outstanding, treasury_shares, equity, bvps, eps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND shares_outstanding IS NOT NULL
          AND disclosed_date <= ?
        ORDER BY current_period_end DESC, disclosed_date DESC
        """,
        conn,
        params=(code, price_date),
    )
    
    print(f"\n全期間のデータ:")
    for idx, row in all_periods.head(5).iterrows():
        shares_net = row["shares_outstanding"] - (row.get("treasury_shares") or 0.0)
        print(f"  {row['current_period_end']} ({row['disclosed_date']}): "
              f"発行済み株式数={shares_net:,.0f}株, 純資産={row['equity']:,.0f}円, "
              f"BPS={row.get('bvps', 0):,.2f}円")
    
    # 2025/3期のデータを取得
    period_2025_03 = "2025-03-31"
    period_data = pd.read_sql_query(
        """
        SELECT shares_outstanding, treasury_shares, equity, current_period_end, disclosed_date, bvps, eps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND current_period_end = ?
          AND shares_outstanding IS NOT NULL
        ORDER BY disclosed_date DESC
        LIMIT 1
        """,
        conn,
        params=(code, period_2025_03),
    )
    
    # 2024/3期のデータも取得（分割前のデータがあるか確認）
    period_2024_03 = "2024-03-31"
    period_2024_data = pd.read_sql_query(
        """
        SELECT shares_outstanding, treasury_shares, equity, current_period_end, disclosed_date, bvps, eps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND current_period_end = ?
          AND shares_outstanding IS NOT NULL
        ORDER BY disclosed_date DESC
        LIMIT 1
        """,
        conn,
        params=(code, period_2024_03),
    )
    
    if period_data.empty:
        print(f"\n{period_2025_03}期のデータが見つかりません")
        sys.exit(1)
    
    period_row = period_data.iloc[0]
    period_shares_outstanding = period_row["shares_outstanding"]
    period_treasury_shares = period_row.get("treasury_shares") or 0.0
    period_equity = period_row["equity"]
    period_shares_net = period_shares_outstanding - period_treasury_shares
    period_bvps = period_row.get("bvps")
    period_eps = period_row.get("eps")
    
    print(f"\n{period_2025_03}期:")
    print(f"  発行済み株式数: {period_shares_outstanding:,.0f}株")
    print(f"  自己株式: {period_treasury_shares:,.0f}株")
    print(f"  発行済み株式数（自己株式除く）: {period_shares_net:,.0f}株")
    print(f"  純資産: {period_equity:,.0f}円")
    print(f"  BPS: {period_bvps:,.2f}円")
    print(f"  EPS: {period_eps:,.2f}円")
    print(f"  開示日: {period_row['disclosed_date']}")
    
    if not period_2024_data.empty:
        period_2024_row = period_2024_data.iloc[0]
        period_2024_shares_outstanding = period_2024_row["shares_outstanding"]
        period_2024_treasury_shares = period_2024_row.get("treasury_shares") or 0.0
        period_2024_equity = period_2024_row["equity"]
        period_2024_shares_net = period_2024_shares_outstanding - period_2024_treasury_shares
        period_2024_bvps = period_2024_row.get("bvps")
        
        print(f"\n{period_2024_03}期（比較用）:")
        print(f"  発行済み株式数（自己株式除く）: {period_2024_shares_net:,.0f}株")
        print(f"  純資産: {period_2024_equity:,.0f}円")
        print(f"  BPS: {period_2024_bvps:,.2f}円")
        
        # 2024/3期と最新期を比較
        shares_ratio_2024 = latest_shares_net / period_2024_shares_net if period_2024_shares_net > 0 else 0
        equity_ratio_2024 = latest_equity / period_2024_equity if period_2024_equity > 0 else 0
        
        print(f"\n2024/3期と最新期の比較:")
        print(f"  発行済み株式数の変化率: {shares_ratio_2024:.3f} ({shares_ratio_2024 * 100:.1f}%)")
        print(f"  純資産の変化率: {equity_ratio_2024:.3f} ({equity_ratio_2024 * 100:.1f}%)")
        
        is_stock_split_2024 = (
            shares_ratio_2024 > 1.0 and
            0.85 <= equity_ratio_2024 <= 1.15
        )
        
        print(f"  株式分割と判定: {is_stock_split_2024}")
        
        if is_stock_split_2024:
            adjustment_factor_2024 = _get_shares_adjustment_factor(
                conn, code, period_2024_03, latest_shares_net, latest_equity
            )
            print(f"  調整係数: {adjustment_factor_2024:.6f}")
    
    # 比率を計算
    shares_ratio = latest_shares_net / period_shares_net if period_shares_net > 0 else 0
    equity_ratio = latest_equity / period_equity if period_equity > 0 else 0
    
    print(f"\n比率:")
    print(f"  発行済み株式数の変化率: {shares_ratio:.3f} ({shares_ratio * 100:.1f}%)")
    print(f"  純資産の変化率: {equity_ratio:.3f} ({equity_ratio * 100:.1f}%)")
    
    # 株式分割の判定条件を確認
    is_stock_split = (
        shares_ratio > 1.0 and
        0.85 <= equity_ratio <= 1.15
    )
    
    print(f"\n株式分割の判定:")
    print(f"  発行済み株式数が増加: {shares_ratio > 1.0} ({shares_ratio:.3f} > 1.0)")
    print(f"  純資産の増加率が0.85以上1.15以下: {0.85 <= equity_ratio <= 1.15} ({equity_ratio:.3f})")
    print(f"  株式分割と判定: {is_stock_split}")
    
    # 調整係数を計算
    adjustment_factor = _get_shares_adjustment_factor(
        conn, code, period_2025_03, latest_shares_net, latest_equity
    )
    
    print(f"\n調整係数: {adjustment_factor:.6f}")
    
    if adjustment_factor != 1.0:
        adjusted_bvps = period_bvps * adjustment_factor if pd.notna(period_bvps) else np.nan
        adjusted_eps = period_eps * adjustment_factor if pd.notna(period_eps) else np.nan
        
        print(f"\n調整後:")
        print(f"  BPS: {period_bvps:,.2f}円 → {adjusted_bvps:,.2f}円")
        print(f"  EPS: {period_eps:,.2f}円 → {adjusted_eps:,.2f}円")
        
        # 現在の価格を取得
        price_data = pd.read_sql_query(
            """
            SELECT adj_close
            FROM prices_daily
            WHERE code = ?
              AND date <= ?
            ORDER BY date DESC
            LIMIT 1
            """,
            conn,
            params=(code, price_date),
        )
        
        if not price_data.empty:
            price = price_data.iloc[0]["adj_close"]
            pbr_original = price / period_bvps if pd.notna(period_bvps) and period_bvps > 0 else np.nan
            pbr_adjusted = price / adjusted_bvps if pd.notna(adjusted_bvps) and adjusted_bvps > 0 else np.nan
            
            print(f"\n価格: {price:,.0f}円")
            print(f"  PBR（調整前）: {pbr_original:.2f}")
            print(f"  PBR（調整後）: {pbr_adjusted:.2f}")
    else:
        print("\n調整係数が1.0のため、調整は適用されませんでした")
