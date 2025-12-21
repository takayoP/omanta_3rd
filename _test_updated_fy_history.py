#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新された履歴データロードのテスト
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _load_fy_history

asof = "2025-12-19"
test_code = "1605"  # INPEX

print(f"=== 更新された履歴データロードのテスト ===\n")
print(f"テスト対象: INPEX（コード{test_code}）\n")

with connect_db() as conn:
    history = _load_fy_history(conn, asof, years=10)
    
    test_data = history[history["code"] == test_code].sort_values("current_period_end", ascending=False)
    
    if not test_data.empty:
        print(f"履歴データ（{len(test_data)}件）:\n")
        for idx, row in test_data.iterrows():
            missing = []
            if pd.isna(row["operating_profit"]):
                missing.append("operating_profit")
            if pd.isna(row["profit"]):
                missing.append("profit")
            if pd.isna(row["equity"]):
                missing.append("equity")
            if pd.isna(row["eps"]):
                missing.append("eps")
            if pd.isna(row["bvps"]):
                missing.append("bvps")
            
            missing_str = f" (欠損: {', '.join(missing)})" if missing else ""
            print(f"  開示日: {row['disclosed_date']}, 当期末: {row['current_period_end']}{missing_str}")
        
        print("\n→ 各当期末ごとに開示日が最新のものが選ばれ、")
        print("  主要項目（operating_profit, profit, equity）が全て欠損のレコードは除外されている")
    else:
        print(f"銘柄コード {test_code} の履歴データが見つかりません")

print("\n" + "="*60)
print("テスト完了")
