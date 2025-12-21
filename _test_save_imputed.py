#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
補完データの保存をテスト
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _load_latest_fy, _save_imputed_fy_to_statements

# テスト実行
asof = "2025-12-19"
print(f"=== 補完データの保存テスト (asof={asof}) ===\n")

with connect_db() as conn:
    # 補完処理を実行
    latest = _load_latest_fy(conn, asof)
    
    # 特定の銘柄コードを確認（保存前）
    test_code = "2130"
    test_row = latest[latest["code"] == test_code]
    
    if not test_row.empty:
        row = test_row.iloc[0]
        print(f"保存前（メモリ内のデータ）:")
        print(f"  銘柄コード: {row['code']}")
        print(f"  開示日: {row['disclosed_date']}")
        print(f"  equity: {row['equity']}")
        print(f"  imputed_equity: {row['imputed_equity']}")
        print(f"  bvps: {row['bvps']}")
        print(f"  imputed_bvps: {row['imputed_bvps']}")
        print()
        
        # 実際に保存処理を実行
        print("_save_imputed_fy_to_statements を実行中...")
        _save_imputed_fy_to_statements(conn, latest)
        conn.commit()
        print("保存完了")
        print()
        
        # 保存後のデータを確認
        saved_row = pd.read_sql_query("""
            SELECT code, disclosed_date, equity, imputed_equity,
                   bvps, imputed_bvps
            FROM fins_statements
            WHERE code = ?
              AND type_of_current_period = 'FY'
              AND disclosed_date = ?
              AND current_period_end = ?
        """, conn, params=(test_code, "2025-05-14", "2025-03-31"))
        
        if not saved_row.empty:
            print(f"保存後（データベース内のデータ）:")
            print(f"  銘柄コード: {saved_row.iloc[0]['code']}")
            print(f"  開示日: {saved_row.iloc[0]['disclosed_date']}")
            print(f"  equity: {saved_row.iloc[0]['equity']}")
            print(f"  imputed_equity: {saved_row.iloc[0]['imputed_equity']}")
            print(f"  bvps: {saved_row.iloc[0]['bvps']}")
            print(f"  imputed_bvps: {saved_row.iloc[0]['imputed_bvps']}")
        else:
            print("保存後のデータが見つかりません")
    else:
        print(f"銘柄コード {test_code} のデータが見つかりません")
