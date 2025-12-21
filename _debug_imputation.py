#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
補完処理のデバッグ
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _load_latest_fy

# テスト実行
asof = "2025-12-19"
print(f"=== _load_latest_fy のテスト実行 (asof={asof}) ===\n")

with connect_db() as conn:
    latest = _load_latest_fy(conn, asof)
    
    # 特定の銘柄コードを確認
    test_code = "2130"
    test_row = latest[latest["code"] == test_code]
    
    if not test_row.empty:
        row = test_row.iloc[0]
        print(f"銘柄コード: {row['code']}")
        print(f"開示日: {row['disclosed_date']}")
        print(f"equity: {row['equity']}")
        print(f"imputed_equity: {row['imputed_equity']}")
        print(f"bvps: {row['bvps']}")
        print(f"imputed_bvps: {row['imputed_bvps']}")
    else:
        print(f"銘柄コード {test_code} のデータが見つかりません")
