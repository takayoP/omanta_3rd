"""
コード7419の予想データとForward PERの計算を確認
"""

from src.omanta_3rd.infra.db import connect_db
import pandas as pd

code = "7419"
asof = "2025-12-19"

print(f"コード {code}（ノジマ）の予想データとForward PERの計算を確認")
print(f"評価日: {asof}")
print("=" * 80)

with connect_db() as conn:
    # 予想データを取得（ROW_NUMBER()方式）
    print("\n【予想データ（ROW_NUMBER()方式、type_of_current_period='FY'）】")
    fc_data = pd.read_sql_query(
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
            AND type_of_current_period = 'FY'
        )
        SELECT code, disclosed_date, type_of_current_period,
               forecast_operating_profit, forecast_profit, forecast_eps,
               next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps
        FROM ranked
        WHERE rn = 1
          AND code = ?
        """,
        conn,
        params=(asof, code),
    )
    print(fc_data)
    if not fc_data.empty:
        print(f"\n詳細:")
        print(f"  forecast_profit: {fc_data.iloc[0].get('forecast_profit')}")
        print(f"  forecast_eps: {fc_data.iloc[0].get('forecast_eps')}")
        print(f"  forecast_operating_profit: {fc_data.iloc[0].get('forecast_operating_profit')}")
    
    # 予想データを取得（type_of_current_period条件なし、forecast_profitが存在するもの）
    print("\n【予想データ（forecast_profitが存在するもの、全期間）】")
    fc_data_with_profit = pd.read_sql_query(
        """
        SELECT code, disclosed_date, type_of_current_period,
               forecast_operating_profit, forecast_profit, forecast_eps,
               next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND disclosed_date <= ?
          AND forecast_profit IS NOT NULL
        ORDER BY disclosed_date DESC
        LIMIT 10
        """,
        conn,
        params=(code, asof),
    )
    print(fc_data_with_profit)
    
    # 予想データを取得（従来方式：disclosed_dateでソート）
    print("\n【予想データ（従来方式：disclosed_date DESC）】")
    fc_data_old = pd.read_sql_query(
        """
        SELECT code, disclosed_date, type_of_current_period,
               forecast_operating_profit, forecast_profit, forecast_eps,
               next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND disclosed_date <= ?
          AND type_of_current_period = 'FY'
          AND (forecast_operating_profit IS NOT NULL 
               OR forecast_profit IS NOT NULL 
               OR forecast_eps IS NOT NULL)
        ORDER BY disclosed_date DESC
        LIMIT 5
        """,
        conn,
        params=(code, asof),
    )
    print(fc_data_old)
    
    # 予想データを取得（type_of_current_period条件なし）
    print("\n【予想データ（type_of_current_period条件なし）】")
    fc_data_all = pd.read_sql_query(
        """
        SELECT code, disclosed_date, type_of_current_period,
               forecast_operating_profit, forecast_profit, forecast_eps,
               next_year_forecast_operating_profit, next_year_forecast_profit, next_year_forecast_eps
        FROM fins_statements
        WHERE code = ?
          AND disclosed_date <= ?
          AND (forecast_operating_profit IS NOT NULL 
               OR forecast_profit IS NOT NULL 
               OR forecast_eps IS NOT NULL)
        ORDER BY disclosed_date DESC, type_of_current_period
        LIMIT 10
        """,
        conn,
        params=(code, asof),
    )
    print(fc_data_all)
    
    # features_monthlyから取得
    print("\n【features_monthlyから取得】")
    feat_data = pd.read_sql_query(
        """
        SELECT as_of_date, code, per, pbr, forward_per, market_cap
        FROM features_monthly
        WHERE code = ?
          AND as_of_date = ?
        """,
        conn,
        params=(code, asof),
    )
    print(feat_data)
    
    # build_featuresのマージ後のデータを確認するため、実際にbuild_featuresを実行して確認
    print("\n【build_features実行後のデータ確認】")
    from src.omanta_3rd.jobs.monthly_run import build_features
    feat = build_features(conn, asof)
    code_feat = feat[feat["code"] == code].copy()
    
    if not code_feat.empty:
        row = code_feat.iloc[0]
        print(f"forecast_profit_fc: {row.get('forecast_profit_fc')}")
        print(f"forward_per: {row.get('forward_per')}")
        print(f"market_cap_latest_basis: {row.get('market_cap_latest_basis')}")
        
        # マージされた予想データのカラムを確認
        forecast_cols = [col for col in code_feat.columns if 'forecast' in col.lower() or 'fc' in col.lower()]
        print(f"\n予想関連カラム: {forecast_cols}")
        for col in forecast_cols:
            print(f"  {col}: {row.get(col)}")
