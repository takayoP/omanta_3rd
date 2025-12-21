#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fins_statementsテーブルのデータを5年分再取得するスクリプト
補完フラグもリセットします
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.ingest.fins import ingest_financial_statements
from omanta_3rd.infra.db import connect_db


def main():
    # 5年前の日付を計算
    today = datetime.now()
    five_years_ago = today - timedelta(days=5 * 365)
    
    date_from = five_years_ago.strftime("%Y-%m-%d")
    date_to = today.strftime("%Y-%m-%d")
    
    print(f"財務データを再取得します")
    print(f"期間: {date_from} ～ {date_to}")
    print(f"（約5年分）")
    print()
    
    # 補完フラグをリセット（データ再取得前に実行）
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
    print("（この処理には時間がかかります）")
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
            count = conn.execute("SELECT COUNT(*) FROM fins_statements").fetchone()[0]
            min_date = conn.execute("SELECT MIN(disclosed_date) FROM fins_statements").fetchone()[0]
            max_date = conn.execute("SELECT MAX(disclosed_date) FROM fins_statements").fetchone()[0]
            
            print()
            print("=== 取得結果 ===")
            print(f"総レコード数: {count:,}件")
            print(f"開示日の範囲: {min_date} ～ {max_date}")
            
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
