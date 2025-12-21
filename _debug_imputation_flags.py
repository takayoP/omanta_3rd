#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
補完フラグのデバッグ
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _fill_fy_missing_with_quarterly

asof = "2025-12-19"
test_code = "2130"

with connect_db() as conn:
    # FYデータを取得
    fy_df = pd.read_sql_query("""
        SELECT *
        FROM fins_statements
        WHERE disclosed_date <= ?
          AND type_of_current_period = 'FY'
          AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL)
          AND code = ?
    """, conn, params=(asof, test_code))
    
    if fy_df.empty:
        print("FYデータが見つかりません")
        sys.exit(1)
    
    fy_df["disclosed_date"] = pd.to_datetime(fy_df["disclosed_date"], errors="coerce")
    fy_df["current_period_end"] = pd.to_datetime(fy_df["current_period_end"], errors="coerce")
    fy_df = fy_df.sort_values(["code", "disclosed_date", "current_period_end"])
    latest = fy_df.groupby("code", as_index=False).tail(1).copy()
    
    print("補完前:")
    row = latest.iloc[0]
    print(f"  equity: {row['equity']} (isna: {pd.isna(row['equity'])})")
    print(f"  imputed_equity: {row.get('imputed_equity', 'N/A')}")
    
    # 補完処理を実行
    result = _fill_fy_missing_with_quarterly(conn, latest.copy(), asof)
    
    print("\n補完後:")
    row = result.iloc[0]
    print(f"  equity: {row['equity']} (isna: {pd.isna(row['equity'])})")
    print(f"  imputed_equity: {row.get('imputed_equity', 'N/A')}")
    print(f"  imputed_equity type: {type(row.get('imputed_equity'))}")
    print(f"  imputed_equity value: {row.get('imputed_equity')}")
