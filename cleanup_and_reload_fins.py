#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fins_statementsテーブルの補完フラグをリセットし、
最新のデータを再取得するスクリプト
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.ingest.fins import ingest_financial_statements
from omanta_3rd.infra.db import connect_db

def main():
    # 過去90日分のデータを再取得（最新データのみ）
    today = datetime.now()
    ninety_days_ago = today - timedelta(days=90)
    
    date_from = ninety_days_ago.strftime("%Y-%m-%d")
    date_to = today.strftime("%Y-%m-%d")
    
    print(f"fins_statementsテーブルの補完フラグをリセットし、最新データを再取得します")
    print(f"期間: {date_from} ～ {date_to}")
    print(f"（過去90日分）")
    print()
    
    # 補完フラグをリセット
    print("補完フラグをリセット中...")
    with connect_db() as conn:
        conn.execute("""
            UPDATE fins_statements
            SET imputed_op = 0,
                imputed_profit = 0,
                imputed_equity = 0,
                imputed_eps = 0,
                imputed_bvps = 0
        """)
        conn.commit()
    print("補完フラグのリセットが完了しました")
    print()
    
    # データを再取得（UPSERTにより既存データは上書きされる）
    print("財務データの取得を開始します...")
    print()
    
    try:
        ingest_financial_statements(date_from=date_from, date_to=date_to)
        print()
        print("財務データの再取得が完了しました")
        
        # 補完フラグを0にリセット（INSERT OR REPLACEでNULLになった可能性があるため）
        print()
        print("補完フラグを最終リセット中...")
        with connect_db() as conn:
            conn.execute("""
                UPDATE fins_statements
                SET imputed_op = COALESCE(imputed_op, 0),
                    imputed_profit = COALESCE(imputed_profit, 0),
                    imputed_equity = COALESCE(imputed_equity, 0),
                    imputed_eps = COALESCE(imputed_eps, 0),
                    imputed_bvps = COALESCE(imputed_bvps, 0)
                WHERE imputed_op IS NULL 
                   OR imputed_profit IS NULL 
                   OR imputed_equity IS NULL 
                   OR imputed_eps IS NULL 
                   OR imputed_bvps IS NULL
            """)
            conn.commit()
        print("補完フラグのリセットが完了しました")
        
        # 取得されたデータ件数を確認
        with connect_db(read_only=True) as conn:
            count = conn.execute("""
                SELECT COUNT(*) FROM fins_statements 
                WHERE disclosed_date >= ? AND disclosed_date <= ?
            """, (date_from, date_to)).fetchone()[0]
            
            print()
            print("=== 取得結果 ===")
            print(f"期間内のレコード数: {count:,}件")
            
            # 補完フラグが立っているレコードを確認
            imputed_count = conn.execute("""
                SELECT COUNT(*) FROM fins_statements
                WHERE type_of_current_period = 'FY'
                  AND (imputed_op = 1 OR imputed_profit = 1 OR imputed_equity = 1 
                       OR imputed_eps = 1 OR imputed_bvps = 1)
            """).fetchone()[0]
            
            print(f"補完フラグが立っているFYレコード: {imputed_count}件")
            if imputed_count == 0:
                print("✓ データはクリーンな状態です")
            
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
