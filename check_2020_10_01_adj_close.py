"""2020-10-01のadj_closeデータを確認"""

from src.omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    # 2020-10-01のadj_closeデータを確認
    print("=" * 80)
    print("2020-10-01のadj_closeデータの状況")
    print("=" * 80)
    
    # adj_closeがNULLでない銘柄数
    adj_close_not_null = pd.read_sql_query(
        "SELECT COUNT(DISTINCT code) as count FROM prices_daily WHERE date = ? AND adj_close IS NOT NULL",
        conn,
        params=("2020-10-01",),
    )
    print(f"adj_closeがNULLでない銘柄数: {adj_close_not_null['count'].iloc[0] if not adj_close_not_null.empty else 0}")
    
    # すべてのカラムがNULLの銘柄数
    all_null = pd.read_sql_query(
        """
        SELECT COUNT(DISTINCT code) as count
        FROM prices_daily
        WHERE date = ?
          AND open IS NULL
          AND close IS NULL
          AND adj_close IS NULL
        """,
        conn,
        params=("2020-10-01",),
    )
    print(f"すべての価格カラムがNULLの銘柄数: {all_null['count'].iloc[0] if not all_null.empty else 0}")
    
    # サンプルデータを確認（最初の10銘柄）
    sample = pd.read_sql_query(
        """
        SELECT code, open, close, adj_close, adj_volume, turnover_value, adjustment_factor
        FROM prices_daily
        WHERE date = ?
        LIMIT 10
        """,
        conn,
        params=("2020-10-01",),
    )
    
    if not sample.empty:
        print(f"\nサンプルデータ（最初の10銘柄）:")
        print(sample.to_string(index=False))
    
    # 前後の日付のデータを確認（2020-09-30と2020-10-02）
    print("\n" + "=" * 80)
    print("前後の日付のデータを確認")
    print("=" * 80)
    
    for check_date in ["2020-09-30", "2020-10-02"]:
        count = pd.read_sql_query(
            "SELECT COUNT(DISTINCT code) as count FROM prices_daily WHERE date = ?",
            conn,
            params=(check_date,),
        )
        open_count = pd.read_sql_query(
            "SELECT COUNT(DISTINCT code) as count FROM prices_daily WHERE date = ? AND open IS NOT NULL",
            conn,
            params=(check_date,),
        )
        print(f"\n{check_date}:")
        print(f"  全銘柄数: {count['count'].iloc[0] if not count.empty else 0}")
        print(f"  openがNULLでない銘柄数: {open_count['count'].iloc[0] if not open_count.empty else 0}")



