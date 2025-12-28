"""データベースに実際にデータが存在するかを確認するスクリプト"""

from src.omanta_3rd.infra.db import connect_db
import pandas as pd

as_of_date = "2025-12-26"

# 分析結果で問題があった銘柄を確認
target_codes = ["1773", "1873", "1963", "2130", "2168", "2198", "2282", "2410", "2503", "2590"]

print("=" * 80)
print("データベース直接確認")
print("=" * 80)
print(f"評価日: {as_of_date}")
print()

with connect_db() as conn:
    for code in target_codes:
        print(f"\n{'=' * 80}")
        print(f"銘柄コード: {code}")
        print(f"{'=' * 80}")
        
        # 1. FYデータの存在確認
        print("\n[1] FYデータ（fins_statements）の確認:")
        fy_data = pd.read_sql_query(
            """
            SELECT 
                disclosed_date,
                type_of_current_period,
                current_period_end,
                operating_profit,
                profit,
                equity,
                eps,
                bvps,
                forecast_operating_profit,
                forecast_profit,
                forecast_eps,
                shares_outstanding,
                treasury_shares
            FROM fins_statements
            WHERE code = ? 
              AND type_of_current_period = 'FY'
              AND disclosed_date <= ?
              AND current_period_end <= ?
            ORDER BY current_period_end DESC, disclosed_date DESC
            LIMIT 5
            """,
            conn,
            params=(code, as_of_date, as_of_date),
        )
        
        if fy_data.empty:
            print("  ❌ FYデータが存在しません")
        else:
            print(f"  ✅ FYデータ: {len(fy_data)}件")
            print("\n  最新のFYデータ:")
            latest = fy_data.iloc[0]
            for col in fy_data.columns:
                val = latest[col]
                if pd.isna(val):
                    print(f"    {col}: NULL")
                else:
                    print(f"    {col}: {val}")
        
        # 2. 価格データの確認
        print("\n[2] 価格データ（prices_daily）の確認:")
        price_data = pd.read_sql_query(
            """
            SELECT date, close, open, adj_close, adj_volume, turnover_value
            FROM prices_daily
            WHERE code = ? AND date <= ?
            ORDER BY date DESC
            LIMIT 5
            """,
            conn,
            params=(code, as_of_date),
        )
        
        if price_data.empty:
            print("  ❌ 価格データが存在しません")
        else:
            print(f"  ✅ 価格データ: {len(price_data)}件")
            print("\n  最新の価格データ:")
            latest_price = price_data.iloc[0]
            for col in price_data.columns:
                val = latest_price[col]
                if pd.isna(val):
                    print(f"    {col}: NULL")
                else:
                    print(f"    {col}: {val}")
        
        # 3. _load_latest_fyと同じロジックで取得されるデータを確認
        print("\n[3] _load_latest_fyロジックで取得されるデータ:")
        df_latest_period = pd.read_sql_query(
            """
            WITH ranked AS (
              SELECT
                code, current_period_end,
                ROW_NUMBER() OVER (
                  PARTITION BY code
                  ORDER BY current_period_end DESC, disclosed_date DESC
                ) AS rn
              FROM fins_statements
              WHERE disclosed_date <= ?
                AND current_period_end <= ?
                AND type_of_current_period = 'FY'
            )
            SELECT code, current_period_end
            FROM ranked
            WHERE rn = 1 AND code = ?
            """,
            conn,
            params=(as_of_date, as_of_date, code),
        )
        
        if df_latest_period.empty:
            print("  ❌ _load_latest_fyで取得されるデータがありません")
        else:
            print(f"  ✅ 最新のcurrent_period_end: {df_latest_period.iloc[0]['current_period_end']}")
            
            # そのcurrent_period_endの全レコードを取得
            period_end = df_latest_period.iloc[0]['current_period_end']
            df_period_records = pd.read_sql_query(
                """
                SELECT
                  fs.disclosed_date, fs.disclosed_time, fs.code, fs.type_of_current_period, fs.current_period_end,
                  fs.operating_profit, fs.profit, fs.equity, fs.eps, fs.bvps,
                  fs.forecast_operating_profit, fs.forecast_profit, fs.forecast_eps,
                  fs.next_year_forecast_operating_profit, fs.next_year_forecast_profit, fs.next_year_forecast_eps,
                  fs.shares_outstanding, fs.treasury_shares
                FROM fins_statements fs
                WHERE fs.code = ?
                  AND fs.current_period_end = ?
                  AND fs.disclosed_date <= ?
                  AND fs.current_period_end <= ?
                  AND fs.type_of_current_period = 'FY'
                ORDER BY fs.disclosed_date DESC
                """,
                conn,
                params=(code, period_end, as_of_date, as_of_date),
            )
            
            if df_period_records.empty:
                print("  ❌ 該当するレコードがありません")
            else:
                print(f"  ✅ 同じcurrent_period_endのレコード: {len(df_period_records)}件")
                print("\n  各レコードの詳細:")
                for idx, row in df_period_records.iterrows():
                    print(f"\n    レコード {idx + 1}:")
                    print(f"      開示日: {row['disclosed_date']}")
                    print(f"      operating_profit: {row['operating_profit']}")
                    print(f"      profit: {row['profit']}")
                    print(f"      equity: {row['equity']}")
                    print(f"      forecast_profit: {row['forecast_profit']}")
                    print(f"      forecast_operating_profit: {row['forecast_operating_profit']}")
        
        # 4. 予想データの確認
        print("\n[4] 予想データ（_load_latest_forecastロジック）の確認:")
        df_forecast = pd.read_sql_query(
            """
            WITH ranked AS (
              SELECT
                code, disclosed_date, type_of_current_period,
                forecast_operating_profit, forecast_profit, forecast_eps,
                next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps,
                ROW_NUMBER() OVER (
                  PARTITION BY code
                  ORDER BY disclosed_date DESC
                ) AS rn
              FROM fins_statements
              WHERE disclosed_date <= ?
                AND current_period_end <= ?
                AND type_of_current_period = 'FY'
                AND (forecast_operating_profit IS NOT NULL 
                     OR forecast_profit IS NOT NULL 
                     OR forecast_eps IS NOT NULL)
            )
            SELECT code, disclosed_date, type_of_current_period,
                   forecast_operating_profit, forecast_profit, forecast_eps,
                   next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps
            FROM ranked
            WHERE rn = 1 AND code = ?
            """,
            conn,
            params=(as_of_date, as_of_date, code),
        )
        
        if df_forecast.empty:
            print("  ❌ FY予想データが存在しません")
            
            # 四半期データを確認
            print("\n  四半期予想データの確認:")
            df_quarter_forecast = pd.read_sql_query(
                """
                WITH ranked AS (
                  SELECT
                    code, disclosed_date, type_of_current_period,
                    forecast_operating_profit, forecast_profit, forecast_eps,
                    next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps,
                    ROW_NUMBER() OVER (
                      PARTITION BY code
                      ORDER BY disclosed_date DESC,
                               CASE 
                                 WHEN type_of_current_period = '3Q' THEN 1
                                 WHEN type_of_current_period = '2Q' THEN 2
                                 WHEN type_of_current_period = '1Q' THEN 3
                                 ELSE 4
                               END
                    ) AS rn
                  FROM fins_statements
                  WHERE disclosed_date <= ?
                    AND type_of_current_period IN ('3Q', '2Q', '1Q')
                    AND (forecast_operating_profit IS NOT NULL 
                         OR forecast_profit IS NOT NULL 
                         OR forecast_eps IS NOT NULL)
                )
                SELECT code, disclosed_date, type_of_current_period,
                       forecast_operating_profit, forecast_profit, forecast_eps,
                       next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps
                FROM ranked
                WHERE rn = 1 AND code = ?
                """,
                conn,
                params=(as_of_date, code),
            )
            
            if df_quarter_forecast.empty:
                print("    ❌ 四半期予想データも存在しません")
            else:
                print(f"    ✅ 四半期予想データ: {len(df_quarter_forecast)}件")
                row = df_quarter_forecast.iloc[0]
                print(f"      type_of_current_period: {row['type_of_current_period']}")
                print(f"      disclosed_date: {row['disclosed_date']}")
                print(f"      forecast_profit: {row['forecast_profit']}")
                print(f"      forecast_operating_profit: {row['forecast_operating_profit']}")
        else:
            print(f"  ✅ FY予想データ: {len(df_forecast)}件")
            row = df_forecast.iloc[0]
            print(f"    disclosed_date: {row['disclosed_date']}")
            print(f"    forecast_profit: {row['forecast_profit']}")
            print(f"    forecast_operating_profit: {row['forecast_operating_profit']}")
            print(f"    forecast_eps: {row['forecast_eps']}")

