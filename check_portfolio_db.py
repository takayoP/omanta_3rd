"""データベース内のポートフォリオを確認"""

from omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    # ポートフォリオの存在確認
    portfolio_df = pd.read_sql_query(
        "SELECT DISTINCT rebalance_date FROM portfolio_monthly ORDER BY rebalance_date",
        conn
    )
    
    print("=" * 80)
    print("データベース内のポートフォリオ確認")
    print("=" * 80)
    print(f"ポートフォリオ数: {len(portfolio_df)}")
    
    if not portfolio_df.empty:
        print(f"\n最初の5日:")
        print(portfolio_df.head().to_string())
        print(f"\n最後の5日:")
        print(portfolio_df.tail().to_string())
        
        # 最適化期間（2021-01-02～2025-12-26）のポートフォリオを確認
        optimization_portfolios = portfolio_df[
            (portfolio_df['rebalance_date'] >= '2021-01-02') &
            (portfolio_df['rebalance_date'] <= '2025-12-26')
        ]
        print(f"\n最適化期間（2021-01-02～2025-12-26）のポートフォリオ数: {len(optimization_portfolios)}")
        
        if not optimization_portfolios.empty:
            print(f"最初: {optimization_portfolios.iloc[0]['rebalance_date']}")
            print(f"最後: {optimization_portfolios.iloc[-1]['rebalance_date']}")
    else:
        print("\n❌ ポートフォリオが見つかりませんでした")

