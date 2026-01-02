"""2020-10-01の価格データを確認"""

from src.omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    # 2020-10-01の全データを確認
    print("=" * 80)
    print("2020-10-01の価格データの状況")
    print("=" * 80)
    
    # 全銘柄数
    all_count = pd.read_sql_query(
        "SELECT COUNT(DISTINCT code) as count FROM prices_daily WHERE date = ?",
        conn,
        params=("2020-10-01",),
    )
    print(f"全銘柄数: {all_count['count'].iloc[0] if not all_count.empty else 0}")
    
    # openがNULLでない銘柄数
    open_not_null = pd.read_sql_query(
        "SELECT COUNT(DISTINCT code) as count FROM prices_daily WHERE date = ? AND open IS NOT NULL",
        conn,
        params=("2020-10-01",),
    )
    print(f"openがNULLでない銘柄数: {open_not_null['count'].iloc[0] if not open_not_null.empty else 0}")
    
    # openがNULLの銘柄数
    open_null = pd.read_sql_query(
        "SELECT COUNT(DISTINCT code) as count FROM prices_daily WHERE date = ? AND open IS NULL",
        conn,
        params=("2020-10-01",),
    )
    print(f"openがNULLの銘柄数: {open_null['count'].iloc[0] if not open_null.empty else 0}")
    
    # closeがNULLでない銘柄数
    close_not_null = pd.read_sql_query(
        "SELECT COUNT(DISTINCT code) as count FROM prices_daily WHERE date = ? AND close IS NOT NULL",
        conn,
        params=("2020-10-01",),
    )
    print(f"closeがNULLでない銘柄数: {close_not_null['count'].iloc[0] if not close_not_null.empty else 0}")
    
    # openがNULLだがcloseがNULLでない銘柄の例（最初の10銘柄）
    open_null_close_not_null = pd.read_sql_query(
        """
        SELECT code, open, close, adj_close
        FROM prices_daily
        WHERE date = ?
          AND open IS NULL
          AND close IS NOT NULL
        LIMIT 10
        """,
        conn,
        params=("2020-10-01",),
    )
    
    if not open_null_close_not_null.empty:
        print(f"\nopenがNULLだがcloseがNULLでない銘柄の例（{len(open_null_close_not_null)}銘柄）:")
        print(open_null_close_not_null.to_string(index=False))
    
    # ポートフォリオの銘柄（2020-09-30のリバランス）を確認
    # ただし、最適化中は一時的に保存されるので、存在しない可能性がある
    portfolio = pd.read_sql_query(
        "SELECT code, weight FROM portfolio_monthly WHERE rebalance_date = ?",
        conn,
        params=("2020-09-30",),
    )
    
    if not portfolio.empty:
        print(f"\n2020-09-30のポートフォリオ銘柄数: {len(portfolio)}")
        print(f"銘柄コード: {portfolio['code'].tolist()}")
        
        # 各銘柄の2020-10-01のデータを確認
        print("\n各銘柄の2020-10-01のデータ:")
        for code in portfolio["code"]:
            price_row = pd.read_sql_query(
                "SELECT open, close, adj_close FROM prices_daily WHERE code = ? AND date = ?",
                conn,
                params=(code, "2020-10-01"),
            )
            if price_row.empty:
                print(f"  ❌ {code}: データが存在しません")
            elif price_row["open"].iloc[0] is None:
                print(f"  ⚠️  {code}: open=NULL, close={price_row['close'].iloc[0]}, adj_close={price_row['adj_close'].iloc[0]}")
            else:
                print(f"  ✅ {code}: open={price_row['open'].iloc[0]:.2f}, close={price_row['close'].iloc[0]:.2f}")
    else:
        print("\n2020-09-30のポートフォリオはデータベースに存在しません（最適化中は一時的に保存されます）")
        
        # デバッグ情報から、問題のあった銘柄コードを確認
        problem_codes = ['2327', '2429', '3050', '3244', '3932']
        print(f"\n問題のあった銘柄コード（デバッグ情報から）: {problem_codes}")
        print("これらの銘柄の2020-10-01のデータを確認:")
        for code in problem_codes:
            price_row = pd.read_sql_query(
                "SELECT open, close, adj_close FROM prices_daily WHERE code = ? AND date = ?",
                conn,
                params=(code, "2020-10-01"),
            )
            if price_row.empty:
                print(f"  ❌ {code}: データが存在しません")
            elif price_row["open"].iloc[0] is None:
                print(f"  ⚠️  {code}: open=NULL, close={price_row['close'].iloc[0]}, adj_close={price_row['adj_close'].iloc[0]}")
            else:
                print(f"  ✅ {code}: open={price_row['open'].iloc[0]:.2f}, close={price_row['close'].iloc[0]:.2f}")

