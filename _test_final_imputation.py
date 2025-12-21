#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
最終テスト: 補完処理が正しく動作するか確認
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _load_latest_fy

asof = "2025-12-19"

print(f"=== 最終テスト: 補完処理の動作確認 ===\n")
print(f"基準日: {asof}\n")

# _load_latest_fyを実行
print("_load_latest_fy を実行中...\n")
with connect_db() as conn:
    latest = _load_latest_fy(conn, asof)
    
    print(f"取得されたFYデータ: {len(latest)}件\n")
    
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
        
        print("\n補完されたレコードのサンプル（最初の5件）:")
        for idx, row in imputed.head(5).iterrows():
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
    
    # データベースに正しく保存されているか確認
    print("\n" + "="*60)
    print("データベースに保存されたデータを確認\n")
    
    with connect_db(read_only=True) as conn:
        db_imputed = pd.read_sql_query("""
            SELECT code, disclosed_date,
                   imputed_op, imputed_profit, imputed_equity, imputed_eps, imputed_bvps
            FROM fins_statements
            WHERE type_of_current_period = 'FY'
              AND (imputed_op = 1 OR imputed_profit = 1 OR imputed_equity = 1 
                   OR imputed_eps = 1 OR imputed_bvps = 1)
        """, conn)
        
        print(f"データベースに保存された補完レコード数: {len(db_imputed)}件")
        
        if len(db_imputed) > 0:
            print("\n補完フラグの内訳（データベース）:")
            print(f"  imputed_op: {db_imputed['imputed_op'].sum()}件")
            print(f"  imputed_profit: {db_imputed['imputed_profit'].sum()}件")
            print(f"  imputed_equity: {db_imputed['imputed_equity'].sum()}件")
            print(f"  imputed_eps: {db_imputed['imputed_eps'].sum()}件")
            print(f"  imputed_bvps: {db_imputed['imputed_bvps'].sum()}件")
            
            # 検証
            print("\n【検証】")
            if len(imputed) == len(db_imputed):
                print("✓ メモリ内のデータとデータベースのデータが一致しています")
            else:
                print(f"✗ メモリ内: {len(imputed)}件, データベース: {len(db_imputed)}件（不一致）")

print("\n" + "="*60)
print("テスト完了")
