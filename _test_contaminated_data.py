#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fins_statementsが汚れていても、fins_fy_rawから正しく補完前データを取得できるかテスト
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.infra.db import connect_db

asof = "2025-12-19"
test_code = "2389"  # bvpsが欠損している銘柄

print(f"=== fins_statementsが汚れても問題なく再実行できるかテスト ===\n")
print(f"基準日: {asof}")
print(f"テスト対象銘柄: {test_code}\n")

with connect_db() as conn:
    # 1. fins_fy_rawの状態を確認（補完前のクリーンなデータ）
    raw_data = pd.read_sql_query("""
        SELECT code, as_of_date, disclosed_date, equity, eps, bvps
        FROM fins_fy_raw
        WHERE code = ?
          AND as_of_date = ?
    """, conn, params=(test_code, asof))
    
    print("【1. fins_fy_rawの状態（補完前のクリーンなデータ）】")
    if not raw_data.empty:
        row = raw_data.iloc[0]
        print(f"  equity: {row['equity']}")
        print(f"  eps: {row['eps']}")
        print(f"  bvps: {row['bvps']} (欠損)")
    else:
        print("  （データなし）")
        sys.exit(1)
    
    # 2. fins_statementsの現在の状態を確認
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
    
    print("\n【2. fins_statementsの現在の状態】")
    if not stmt_before.empty:
        row = stmt_before.iloc[0]
        print(f"  disclosed_date: {row['disclosed_date']}")
        print(f"  equity: {row['equity']}")
        print(f"  eps: {row['eps']}")
        print(f"  bvps: {row['bvps']}")
        print(f"  補完フラグ: equity={row['imputed_equity']}, "
              f"eps={row['imputed_eps']}, "
              f"bvps={row['imputed_bvps']}")
        
        # 3. fins_statementsのデータを意図的に汚す（bvpsを補完された値に変更、フラグも1に）
        print("\n【3. fins_statementsのデータを意図的に汚す】")
        print("  bvpsを999999.0に変更し、imputed_bvpsを1に設定")
        
        conn.execute("""
            UPDATE fins_statements
            SET bvps = 999999.0,
                imputed_bvps = 1
            WHERE code = ?
              AND type_of_current_period = 'FY'
              AND disclosed_date = ?
        """, (test_code, row['disclosed_date']))
        conn.commit()
        
        # 4. 汚した後の状態を確認
        stmt_contaminated = pd.read_sql_query("""
            SELECT code, disclosed_date, equity, eps, bvps,
                   imputed_equity, imputed_eps, imputed_bvps
            FROM fins_statements
            WHERE code = ?
              AND type_of_current_period = 'FY'
              AND disclosed_date = ?
        """, conn, params=(test_code, row['disclosed_date']))
        
        print("\n【4. 汚した後のfins_statementsの状態】")
        if not stmt_contaminated.empty:
            row_cont = stmt_contaminated.iloc[0]
            print(f"  bvps: {row_cont['bvps']} (汚染された値)")
            print(f"  imputed_bvps: {row_cont['imputed_bvps']} (汚染されたフラグ)")
    else:
        print("  （データなし）")
        sys.exit(1)

print("\n" + "="*60)
print("_load_latest_fy を実行（fins_fy_rawから補完前データを取得）...\n")

# 5. _load_latest_fyを実行（fins_fy_rawから補完前データを取得するはず）
from omanta_3rd.jobs.monthly_run import _load_latest_fy

with connect_db() as conn:
    latest = _load_latest_fy(conn, asof)
    
    test_row = latest[latest["code"] == test_code]
    
    if not test_row.empty:
        row_result = test_row.iloc[0]
        print("【5. _load_latest_fy実行後の結果】")
        print(f"銘柄コード: {row_result['code']}")
        print(f"開示日: {row_result['disclosed_date']}")
        print(f"  equity: {row_result['equity']}")
        print(f"  eps: {row_result['eps']}")
        print(f"  bvps: {row_result['bvps']} (imputed: {row_result['imputed_bvps']})")
        
        # 6. 検証
        print("\n【6. 検証】")
        # fins_fy_rawから取得したデータが使われているか確認（bvpsがNone/NaNのはず）
        if pd.isna(row_result['bvps']) or row_result['bvps'] is None:
            print("✓ fins_fy_rawから補完前データ（bvps=欠損）が正しく取得されています")
        else:
            print(f"✗ bvpsが{row_result['bvps']}になっています（fins_fy_rawから取得されていない可能性）")
        
        # 補完処理が実行されるかは、四半期データにbvpsがあるかによる
        if row_result['imputed_bvps'] == 1:
            print("✓ bvpsが補完されました（四半期データから補完）")
        else:
            print("  bvpsは補完されませんでした（四半期データにも欠損があるか、補完不可能）")
    else:
        print(f"銘柄コード {test_code} のデータが見つかりません")

print("\n" + "="*60)
print("テスト完了")
