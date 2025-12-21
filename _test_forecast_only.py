#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
予想データのみを使用する実装のテスト
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _load_latest_fy

asof = "2025-12-19"

print(f"=== 予想データのみを使用する実装のテスト ===\n")
print(f"基準日: {asof}\n")

# _load_latest_fyを実行
print("_load_latest_fy を実行中...\n")
with connect_db() as conn:
    latest = _load_latest_fy(conn, asof)
    
    # 補完されたレコードを確認
    imputed = latest[
        (latest["imputed_op"] == 1) |
        (latest["imputed_profit"] == 1) |
        (latest["imputed_equity"] == 1) |
        (latest["imputed_eps"] == 1) |
        (latest["imputed_bvps"] == 1)
    ]
    
    print(f"補完されたレコード数: {len(imputed)}件\n")
    
    if len(imputed) > 0:
        print("補完された項目の内訳:")
        print(f"  operating_profit (imputed_op): {imputed['imputed_op'].sum()}件")
        print(f"  profit (imputed_profit): {imputed['imputed_profit'].sum()}件")
        print(f"  equity (imputed_equity): {imputed['imputed_equity'].sum()}件")
        print(f"  eps (imputed_eps): {imputed['imputed_eps'].sum()}件")
        print(f"  bvps (imputed_bvps): {imputed['imputed_bvps'].sum()}件")
        
        print("\n補完されたレコードのサンプル（最初の10件）:")
        for idx, row in imputed.head(10).iterrows():
            imputed_items = []
            if row["imputed_op"] == 1:
                imputed_items.append(f"operating_profit={row['operating_profit']}")
            if row["imputed_profit"] == 1:
                imputed_items.append(f"profit={row['profit']}")
            if row["imputed_equity"] == 1:
                imputed_items.append(f"equity={row['equity']}")
            if row["imputed_eps"] == 1:
                imputed_items.append(f"eps={row['eps']}")
            if row["imputed_bvps"] == 1:
                imputed_items.append(f"bvps={row['bvps']}")
            
            print(f"  銘柄コード: {row['code']}, 開示日: {row['disclosed_date']}")
            print(f"    補完された項目: {', '.join(imputed_items)}")

print("\n" + "="*60)
print("テスト完了")
print("\n【確認事項】")
print("operating_profit, profit, epsが補完された場合は、")
print("四半期データの予想データ（forecast）のみが使用されていることを確認してください。")
