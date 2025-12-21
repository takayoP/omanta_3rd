#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
開示日基準の選択ロジックのテスト
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _load_latest_fy

asof = "2025-12-19"

print("=== 開示日基準の選択ロジックのテスト ===\n")
print(f"基準日: {asof}\n")

# テスト対象の銘柄（会計基準変更がある銘柄など）
test_codes = ["1605", "1301", "1960"]

with connect_db() as conn:
    latest = _load_latest_fy(conn, asof)
    
    print("【選ばれたデータ】\n")
    for test_code in test_codes:
        test_row = latest[latest["code"] == test_code]
        if not test_row.empty:
            row = test_row.iloc[0]
            print(f"銘柄コード: {row['code']}")
            print(f"  開示日: {row['disclosed_date']}")
            print(f"  当期末: {row['current_period_end']}")
            print(f"  operating_profit: {row['operating_profit']}")
            print(f"  profit: {row['profit']}")
            
            # 欠損があるか確認
            missing = []
            if pd.isna(row.get("operating_profit")):
                missing.append("operating_profit")
            if pd.isna(row.get("profit")):
                missing.append("profit")
            if pd.isna(row.get("equity")):
                missing.append("equity")
            if missing:
                print(f"  ⚠ 欠損項目: {', '.join(missing)}")
            else:
                print(f"  ✓ 主要項目に欠損なし")
            print()

print("="*60)
print("【確認】")
print("開示日が最新のものが選ばれ、主要項目（operating_profit, profit, equity）")
print("が全て欠損のレコードは除外されていることを確認してください。")
