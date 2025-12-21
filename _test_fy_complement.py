#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FYデータの相互補完機能のテスト
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _load_latest_fy

asof = "2025-12-19"

print("=== FYデータの相互補完機能のテスト ===\n")
print(f"基準日: {asof}\n")

# テスト対象の銘柄（相互補完可能なケース）
test_codes = ["6191", "1960", "2928"]

with connect_db() as conn:
    latest = _load_latest_fy(conn, asof)
    
    print("【補完後のデータ】\n")
    for test_code in test_codes:
        test_row = latest[latest["code"] == test_code]
        if not test_row.empty:
            row = test_row.iloc[0]
            print(f"銘柄コード: {row['code']}")
            print(f"  開示日: {row['disclosed_date']}")
            print(f"  当期末: {row['current_period_end']}")
            print(f"  operating_profit: {row['operating_profit'] if pd.notna(row['operating_profit']) else 'NULL'}")
            print(f"  forecast_operating_profit: {row['forecast_operating_profit'] if pd.notna(row['forecast_operating_profit']) else 'NULL'}")
            print(f"  profit: {row['profit'] if pd.notna(row['profit']) else 'NULL'}")
            print(f"  forecast_profit: {row['forecast_profit'] if pd.notna(row['forecast_profit']) else 'NULL'}")
            print(f"  forecast_eps: {row['forecast_eps'] if pd.notna(row['forecast_eps']) else 'NULL'}")
            print()

print("="*60)
print("【確認】")
print("同じcurrent_period_endのFYデータ間で相互補完が行われていることを確認してください。")
