"""2020-10-01の価格データを確認"""

from src.omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    # 2020-10-01の価格データがある銘柄数を確認
    df = pd.read_sql_query(
        "SELECT COUNT(DISTINCT code) as count FROM prices_daily WHERE date = ?",
        conn,
        params=("2020-10-01",),
    )
    print(f"2020-10-01の価格データがある全銘柄数: {df['count'].iloc[0] if not df.empty else 0}")
    
    # 2020-09-30のリバランス日のポートフォリオを確認（存在する場合）
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
                "SELECT open, close FROM prices_daily WHERE code = ? AND date = ?",
                conn,
                params=(code, "2020-10-01"),
            )
            if price_row.empty:
                print(f"  ❌ {code}: データが存在しません")
            elif price_row["open"].iloc[0] is None:
                print(f"  ⚠️  {code}: 始値がNULL（終値: {price_row['close'].iloc[0]}）")
            else:
                print(f"  ✅ {code}: 始値={price_row['open'].iloc[0]:.2f}")
    else:
        print("\n2020-09-30のポートフォリオはデータベースに存在しません（最適化中は一時的に保存されます）")











