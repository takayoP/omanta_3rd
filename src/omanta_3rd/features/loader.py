"""DBからのデータ読み込みヘルパー関数"""

from __future__ import annotations

import pandas as pd

from .adjustments import _get_shares_adjustment_factor
from ..infra.db import upsert


def _snap_price_date(conn, asof: str) -> str:
    row = conn.execute(
        "SELECT MAX(date) AS d FROM prices_daily WHERE date <= ?",
        (asof,),
    ).fetchone()
    d = row["d"] if row else None
    if not d:
        raise RuntimeError(f"No prices_daily.date <= {asof}. Load prices first.")
    return d


def _snap_listed_date(conn, asof: str) -> str:
    row = conn.execute(
        "SELECT MAX(date) AS d FROM listed_info WHERE date <= ?",
        (asof,),
    ).fetchone()
    d = row["d"] if row else None
    if not d:
        row2 = conn.execute("SELECT MAX(date) AS d FROM listed_info").fetchone()
        d = row2["d"] if row2 else None
    if not d:
        raise RuntimeError("listed_info is empty. Run listed ETL.")
    return d


def _load_universe(conn, listed_date: str) -> pd.DataFrame:
    """
    プライム市場（旧：東証一部）の銘柄を取得

    市場区分の変遷:
    - 2022年4月以前: 「東証一部」「東証二部」「マザーズ」など
    - 2022年4月以降: 「プライム」「スタンダード」「グロース」など

    プライム市場 = 「プライム」「Prime」「東証一部」
    """
    df = pd.read_sql_query(
        """
        SELECT code, company_name, market_name, sector17, sector33
        FROM listed_info
        WHERE date = ?
        """,
        conn,
        params=(listed_date,),
    )
    market_name_series = df["market_name"].astype(str)
    is_prime = (
        market_name_series.str.contains("プライム|Prime", case=False, na=False) |
        market_name_series.str.contains("東証一部", na=False)
    )
    df = df[is_prime].copy()
    return df


def _load_prices_window(conn, price_date: str, lookback_days: int = 200) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT date, code, close, adj_close, turnover_value
        FROM prices_daily
        WHERE date <= ?
        """,
        conn,
        params=(price_date,),
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["code", "date"])
    df = df.groupby("code", group_keys=False).tail(lookback_days)
    return df


def _save_fy_to_statements(conn, fy_df: pd.DataFrame):
    """
    FYデータをfins_statementsテーブルに保存

    Args:
        conn: データベース接続
        fy_df: FYデータのDataFrame
    """
    if fy_df.empty:
        return

    save_data = []
    for _, row in fy_df.iterrows():
        disclosed_date = row["disclosed_date"]
        if pd.notna(disclosed_date):
            if hasattr(disclosed_date, 'strftime'):
                disclosed_date = disclosed_date.strftime("%Y-%m-%d")
            else:
                disclosed_date = str(disclosed_date)
        else:
            disclosed_date = None

        current_period_end = row["current_period_end"]
        if pd.notna(current_period_end):
            if hasattr(current_period_end, 'strftime'):
                current_period_end = current_period_end.strftime("%Y-%m-%d")
            else:
                current_period_end = str(current_period_end)
        else:
            current_period_end = None

        save_row = {
            "disclosed_date": disclosed_date,
            "disclosed_time": row.get("disclosed_time"),
            "code": str(row["code"]),
            "type_of_current_period": row.get("type_of_current_period", "FY"),
            "current_period_end": current_period_end,
            "operating_profit": row.get("operating_profit") if pd.notna(row.get("operating_profit")) else None,
            "profit": row.get("profit") if pd.notna(row.get("profit")) else None,
            "equity": row.get("equity") if pd.notna(row.get("equity")) else None,
            "eps": row.get("eps") if pd.notna(row.get("eps")) else None,
            "bvps": row.get("bvps") if pd.notna(row.get("bvps")) else None,
            "forecast_operating_profit": row.get("forecast_operating_profit") if pd.notna(row.get("forecast_operating_profit")) else None,
            "forecast_profit": row.get("forecast_profit") if pd.notna(row.get("forecast_profit")) else None,
            "forecast_eps": row.get("forecast_eps") if pd.notna(row.get("forecast_eps")) else None,
            "next_year_forecast_operating_profit": row.get("next_year_forecast_operating_profit") if pd.notna(row.get("next_year_forecast_operating_profit")) else None,
            "next_year_forecast_profit": row.get("next_year_forecast_profit") if pd.notna(row.get("next_year_forecast_profit")) else None,
            "next_year_forecast_eps": row.get("next_year_forecast_eps") if pd.notna(row.get("next_year_forecast_eps")) else None,
            "shares_outstanding": row.get("shares_outstanding") if pd.notna(row.get("shares_outstanding")) else None,
            "treasury_shares": row.get("treasury_shares") if pd.notna(row.get("treasury_shares")) else None,
        }
        save_data.append(save_row)

    upsert(
        conn,
        "fins_statements",
        save_data,
        conflict_columns=["disclosed_date", "code", "type_of_current_period", "current_period_end"],
    )


def _load_latest_fy(conn, asof: str) -> pd.DataFrame:
    """
    最新のFY実績データを取得（銘柄ごとに最新1件をSQLで確定）
    計算日（asof）以前のFYデータを使用し、開示日が最新のものを選ぶ

    同じcurrent_period_endのFYデータ間で相互補完を行う：
    - 実績値が欠損している場合、他のFYレコードから実績値を補完
    - 予想値が欠損している場合、他のFYレコードから予想値を補完
    """
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
        WHERE rn = 1
        """,
        conn,
        params=(asof, asof),
    )

    if df_latest_period.empty:
        return pd.DataFrame()

    df = pd.read_sql_query(
        """
        WITH latest AS (
          SELECT
            code, current_period_end
          FROM (
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
          WHERE rn = 1
        )
        SELECT
          fs.disclosed_date, fs.disclosed_time, fs.code, fs.type_of_current_period, fs.current_period_end,
          fs.operating_profit, fs.profit, fs.equity, fs.eps, fs.bvps,
          fs.forecast_operating_profit, fs.forecast_profit, fs.forecast_eps,
          fs.next_year_forecast_operating_profit, fs.next_year_forecast_profit, fs.next_year_forecast_eps,
          fs.shares_outstanding, fs.treasury_shares
        FROM fins_statements fs
        JOIN latest l
          ON fs.code = l.code
         AND fs.current_period_end = l.current_period_end
        WHERE fs.disclosed_date <= ?
          AND fs.current_period_end <= ?
          AND fs.type_of_current_period = 'FY'
        """,
        conn,
        params=(asof, asof, asof, asof),
    )
    if df.empty:
        return pd.DataFrame()

    df["disclosed_date"] = pd.to_datetime(df["disclosed_date"], errors="coerce")
    df["current_period_end"] = pd.to_datetime(df["current_period_end"], errors="coerce")

    result_rows = []
    for (code, period_end), group in df.groupby(["code", "current_period_end"]):
        group_sorted = group.sort_values("disclosed_date", ascending=False)
        base_row = group_sorted.iloc[0].copy()

        for col in ["operating_profit", "forecast_operating_profit", "profit", "forecast_profit",
                    "eps", "forecast_eps", "equity", "bvps", "shares_outstanding", "treasury_shares"]:
            if pd.isna(base_row.get(col)):
                for _, row in group_sorted.iterrows():
                    if pd.notna(row.get(col)):
                        base_row[col] = row[col]
                        break

        result_rows.append(base_row)

    if not result_rows:
        return pd.DataFrame()

    result_df = pd.DataFrame(result_rows)

    def _has_actuals(row):
        return (
            pd.notna(row.get("operating_profit")) or
            pd.notna(row.get("profit")) or
            pd.notna(row.get("equity"))
        )

    result_df["has_actuals"] = result_df.apply(_has_actuals, axis=1)
    result_df = result_df.sort_values(["code", "has_actuals", "current_period_end"], ascending=[True, False, False])
    latest = result_df.groupby("code", as_index=False).head(1).copy()
    latest = latest.drop(columns=["has_actuals"])

    return latest


def _load_fy_history(conn, asof: str, years: int = 10) -> pd.DataFrame:
    """
    過去のFY実績データを取得（最大years年分）
    各current_period_endごとに開示日が最新のものを選ぶ

    重要: current_period_end <= asof の条件を追加（計算日より後の期末日のデータは除外）
    """
    df = pd.read_sql_query(
        """
        SELECT code, disclosed_date, current_period_end,
               operating_profit, profit, equity, eps, bvps,
               shares_outstanding, treasury_shares
        FROM fins_statements
        WHERE disclosed_date <= ?
          AND current_period_end <= ?
          AND type_of_current_period = 'FY'
          AND (operating_profit IS NOT NULL OR profit IS NOT NULL OR equity IS NOT NULL)
        """,
        conn,
        params=(asof, asof),
    )
    if df.empty:
        return df

    df["disclosed_date"] = pd.to_datetime(df["disclosed_date"], errors="coerce")
    df["current_period_end"] = pd.to_datetime(df["current_period_end"], errors="coerce")
    df = df.sort_values(["code", "current_period_end", "disclosed_date"])
    df = df.groupby(["code", "current_period_end"], as_index=False).tail(1)
    df = df.sort_values(["code", "current_period_end"], ascending=[True, False])
    df = df.groupby("code", group_keys=False).head(years)

    if not df.empty:
        latest_shares_map = {}
        latest_equity_map = {}
        for code in df["code"].unique():
            code_data = df[df["code"] == code].sort_values("current_period_end", ascending=False)
            if not code_data.empty:
                latest_row = code_data.iloc[0]
                shares_outstanding = latest_row.get("shares_outstanding")
                treasury_shares = latest_row.get("treasury_shares") or 0.0
                equity = latest_row.get("equity")
                if pd.notna(shares_outstanding):
                    latest_shares_map[code] = shares_outstanding - treasury_shares
                if pd.notna(equity):
                    latest_equity_map[code] = equity

        def _adjust_hist_bps_eps(row):
            code = row.get("code")
            period_end = row.get("current_period_end")
            latest_shares = latest_shares_map.get(code)
            latest_equity = latest_equity_map.get(code)

            if pd.isna(period_end) or not code or latest_shares is None or latest_shares <= 0 or latest_equity is None or latest_equity <= 0:
                return row.get("bvps"), row.get("eps")

            if hasattr(period_end, 'strftime'):
                period_end_str = period_end.strftime("%Y-%m-%d")
            else:
                period_end_str = str(period_end)

            adjustment_factor = _get_shares_adjustment_factor(conn, code, period_end_str, latest_shares, latest_equity)

            bvps = row.get("bvps")
            eps = row.get("eps")

            adjusted_bvps = bvps * adjustment_factor if pd.notna(bvps) and adjustment_factor != 1.0 else bvps
            adjusted_eps = eps * adjustment_factor if pd.notna(eps) and adjustment_factor != 1.0 else eps

            return adjusted_bvps, adjusted_eps

        adjusted_hist_values = df.apply(_adjust_hist_bps_eps, axis=1)
        df["bvps"] = adjusted_hist_values.apply(lambda x: x[0])
        df["eps"] = adjusted_hist_values.apply(lambda x: x[1])

    return df


def _load_latest_forecast(conn, asof: str) -> pd.DataFrame:
    """
    最新の予想データを取得（銘柄ごとに最新1件をSQLで確定）

    予測値についてはFY行にデータがなければ四半期データも3Q→2Q→1Qの順で採用する。

    優先順位:
    1. FYデータ（開示日が最新のもの、予想値があるもの）
    2. 四半期データ（3Q → 2Q → 1Qの順、開示日が最新のもの）
    """
    df_fy = pd.read_sql_query(
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
        WHERE rn = 1
        """,
        conn,
        params=(asof, asof),
    )

    codes_with_fy_forecast = set(df_fy["code"].tolist()) if not df_fy.empty else set()

    df_quarter = pd.read_sql_query(
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
        WHERE rn = 1
        """,
        conn,
        params=(asof,),
    )

    if not df_quarter.empty:
        df_quarter = df_quarter[~df_quarter["code"].isin(codes_with_fy_forecast)]

    if df_fy.empty and df_quarter.empty:
        return pd.DataFrame()
    elif df_fy.empty:
        df = df_quarter
    elif df_quarter.empty:
        df = df_fy
    else:
        df = pd.concat([df_fy, df_quarter], ignore_index=True)

    df["disclosed_date"] = pd.to_datetime(df["disclosed_date"], errors="coerce")
    return df
