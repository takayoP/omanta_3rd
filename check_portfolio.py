from omanta_3rd.infra.db import connect_db
import pandas as pd

with connect_db() as conn:
    df = pd.read_sql_query('SELECT COUNT(*) as cnt FROM portfolio_monthly', conn)
    print(f'Portfolio count: {df.iloc[0]["cnt"]}')
    
    if df.iloc[0]["cnt"] > 0:
        dates_df = pd.read_sql_query('SELECT DISTINCT rebalance_date FROM portfolio_monthly ORDER BY rebalance_date LIMIT 5', conn)
        print(f'Sample dates: {dates_df["rebalance_date"].tolist()}')





