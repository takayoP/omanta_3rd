#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新されたロジックのテスト
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _load_latest_fy

asof = "2025-12-19"
test_code = "1605"  # INPEX

print(f"=== 更新されたロジックのテスト ===\n")
print(f"テスト対象: INPEX（コード{test_code}）\n")

with connect_db() as conn:
    latest = _load_latest_fy(conn, asof)
    
    test_row = latest[latest["code"] == test_code]
    
    if not test_row.empty:
        row = test_row.iloc[0]
        print("【選ばれたデータ】")
        print(f"銘柄コード: {row['code']}")
        print(f"開示日: {row['disclosed_date']}")
        print(f"当期末: {row['current_period_end']}")
        print(f"operating_profit: {row['operating_profit']}")
        print(f"profit: {row['profit']}")
        print()
        print("→ 当期末が最新（2024-12-31）で、その中で開示日が最新のものが選ばれているはず")
    else:
        print(f"銘柄コード {test_code} のデータが見つかりません")

print("\n" + "="*60)
print("テスト完了")
