#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fins_fy_rawから補完前データを取得する実装のテスト
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import _load_latest_fy

asof = "2025-12-19"
test_code = "2130"  # equityが欠損しているケース

print(f"=== fins_fy_rawから補完前データを取得する実装のテスト ===\n")
print(f"基準日: {asof}")
print(f"テスト対象銘柄: {test_code}\n")

# テスト前の状態を確認
with connect_db(read_only=True) as conn:
    # fins_fy_rawの状態
    raw_before = pd.read_sql_query("""
        SELECT code, as_of_date, disclosed_date, equity, eps, bvps
        FROM fins_fy_raw
        WHERE code = ?
          AND as_of_date = ?
    """, conn, params=(test_code, asof))
    
    print("【テスト前】")
    print(f"fins_fy_rawのデータ:")
    if not raw_before.empty:
        print(f"  equity: {raw_before.iloc[0]['equity']}")
        print(f"  eps: {raw_before.iloc[0]['eps']}")
        print(f"  bvps: {raw_before.iloc[0]['bvps']}")
    else:
        print("  （データなし）")
    
    # fins_statementsの状態
    stmt_before = pd.read_sql_query("""
        SELECT code, disclosed_date, equity, eps, bvps,
               imputed_equity, imputed_eps, imputed_bvps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND disclosed_date = (SELECT MAX(disclosed_date) FROM fins_statements 
                                 WHERE code = ? AND type_of_current_period = 'FY' 
                                 AND disclosed_date <= ?)
    """, conn, params=(test_code, test_code, asof))
    
    print(f"\nfins_statementsのデータ（最新）:")
    if not stmt_before.empty:
        print(f"  disclosed_date: {stmt_before.iloc[0]['disclosed_date']}")
        print(f"  equity: {stmt_before.iloc[0]['equity']}")
        print(f"  eps: {stmt_before.iloc[0]['eps']}")
        print(f"  bvps: {stmt_before.iloc[0]['bvps']}")
        print(f"  補完フラグ: equity={stmt_before.iloc[0]['imputed_equity']}, "
              f"eps={stmt_before.iloc[0]['imputed_eps']}, "
              f"bvps={stmt_before.iloc[0]['imputed_bvps']}")
    else:
        print("  （データなし）")

print("\n" + "="*60)
print("_load_latest_fy を実行中...\n")

# _load_latest_fyを実行
with connect_db() as conn:
    latest = _load_latest_fy(conn, asof)
    
    # テスト対象の銘柄を確認
    test_row = latest[latest["code"] == test_code]
    
    if not test_row.empty:
        row = test_row.iloc[0]
        print("【実行結果】")
        print(f"銘柄コード: {row['code']}")
        print(f"開示日: {row['disclosed_date']}")
        print(f"equity: {row['equity']} (imputed: {row['imputed_equity']})")
        print(f"eps: {row['eps']} (imputed: {row['imputed_eps']})")
        print(f"bvps: {row['bvps']} (imputed: {row['imputed_bvps']})")
    else:
        print(f"銘柄コード {test_code} のデータが見つかりません")

print("\n" + "="*60)
print("【テスト後】データベースの状態を確認\n")

# テスト後の状態を確認
with connect_db(read_only=True) as conn:
    # fins_fy_rawの状態（変更なしのはず）
    raw_after = pd.read_sql_query("""
        SELECT code, as_of_date, disclosed_date, equity, eps, bvps
        FROM fins_fy_raw
        WHERE code = ?
          AND as_of_date = ?
    """, conn, params=(test_code, asof))
    
    print("fins_fy_rawのデータ（変更なしのはず）:")
    if not raw_after.empty:
        print(f"  equity: {raw_after.iloc[0]['equity']}")
        print(f"  eps: {raw_after.iloc[0]['eps']}")
        print(f"  bvps: {raw_after.iloc[0]['bvps']}")
    else:
        print("  （データなし）")
    
    # fins_statementsの状態（補完後のデータが保存されているはず）
    stmt_after = pd.read_sql_query("""
        SELECT code, disclosed_date, equity, eps, bvps,
               imputed_equity, imputed_eps, imputed_bvps
        FROM fins_statements
        WHERE code = ?
          AND type_of_current_period = 'FY'
          AND disclosed_date = (SELECT MAX(disclosed_date) FROM fins_statements 
                                 WHERE code = ? AND type_of_current_period = 'FY' 
                                 AND disclosed_date <= ?)
    """, conn, params=(test_code, test_code, asof))
    
    print(f"\nfins_statementsのデータ（補完後のデータが保存されているはず）:")
    if not stmt_after.empty:
        print(f"  disclosed_date: {stmt_after.iloc[0]['disclosed_date']}")
        print(f"  equity: {stmt_after.iloc[0]['equity']}")
        print(f"  eps: {stmt_after.iloc[0]['eps']}")
        print(f"  bvps: {stmt_after.iloc[0]['bvps']}")
        print(f"  補完フラグ: equity={stmt_after.iloc[0]['imputed_equity']}, "
              f"eps={stmt_after.iloc[0]['imputed_eps']}, "
              f"bvps={stmt_after.iloc[0]['imputed_bvps']}")
        
        # 検証
        print("\n【検証】")
        if stmt_after.iloc[0]['equity'] is not None and stmt_after.iloc[0]['imputed_equity'] == 1:
            print("✓ equityが補完されています")
        elif stmt_after.iloc[0]['equity'] is None and (raw_after.empty or raw_after.iloc[0]['equity'] is None):
            print("✓ equityは補完できませんでした（元データにも欠損）")
        else:
            print("✗ equityの補完に問題がある可能性があります")
    else:
        print("  （データなし）")

print("\n" + "="*60)
print("テスト完了")
