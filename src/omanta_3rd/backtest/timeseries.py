"""
時系列P/L計算モジュール

月次リバランス戦略としての正しい時系列リターンを計算します。
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

from ..infra.db import connect_db
from .performance import _split_multiplier_between, _get_next_trading_day
from ..ingest.indices import TOPIX_CODE


def _get_previous_trading_day(conn, date: str) -> Optional[str]:
    """
    指定日付の前営業日を取得
    
    Args:
        conn: データベース接続
        date: 基準日（YYYY-MM-DD）
    
    Returns:
        前営業日（YYYY-MM-DD）、存在しない場合はNone
    """
    prev_date_df = pd.read_sql_query(
        """
        SELECT MAX(date) AS prev_date
        FROM prices_daily
        WHERE date < ?
        """,
        conn,
        params=(date,),
    )
    
    if prev_date_df.empty or pd.isna(prev_date_df["prev_date"].iloc[0]):
        return None
    
    return str(prev_date_df["prev_date"].iloc[0])


def _get_topix_price_exact(conn, date: str, use_open: bool = False) -> Optional[float]:
    """
    指定日のTOPIX価格を取得（完全一致）
    
    【重要】完全一致を要求します。データ欠損時はNoneを返します。
    
    Args:
        conn: データベース接続
        date: 日付（YYYY-MM-DD、完全一致を要求）
        use_open: Trueの場合は始値、Falseの場合は終値を取得
    
    Returns:
        TOPIX価格（始値または終値）、存在しない場合はNone
    """
    price_column = "open" if use_open else "close"
    price_df = pd.read_sql_query(
        f"""
        SELECT {price_column}
        FROM index_daily
        WHERE index_code = ? AND date = ?
        """,
        conn,
        params=(TOPIX_CODE, date),
    )
    
    if price_df.empty or pd.isna(price_df[price_column].iloc[0]):
        return None
    
    return float(price_df[price_column].iloc[0])


def _get_price(conn, code: str, date: str, use_open: bool = False) -> Optional[float]:
    """
    指定日の価格を取得（完全一致）
    
    【重要】完全一致を要求します。データ欠損時はNoneを返し、
    その銘柄は当月の取引から除外されます（ウェイト再正規化）。
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        date: 日付（YYYY-MM-DD、完全一致を要求）
        use_open: Trueの場合は始値、Falseの場合は終値を取得
    
    Returns:
        価格、存在しない場合はNone
    """
    price_column = "open" if use_open else "close"
    price_df = pd.read_sql_query(
        f"""
        SELECT {price_column}
        FROM prices_daily
        WHERE code = ? AND date = ?
        """,
        conn,
        params=(code, date),
    )
    
    if price_df.empty or pd.isna(price_df[price_column].iloc[0]):
        return None
    
    return float(price_df[price_column].iloc[0])


def _get_prices_bulk(
    conn, codes: List[str], dates: List[str], use_open: bool = False
) -> pd.DataFrame:
    """
    複数銘柄×複数日付の価格を一括取得（バルクSQL）
    
    Args:
        conn: データベース接続
        codes: 銘柄コードのリスト
        dates: 日付のリスト（YYYY-MM-DD）
        use_open: Trueの場合は始値、Falseの場合は終値を取得
    
    Returns:
        DataFrame (code, date, price列)
    """
    if not codes or not dates:
        return pd.DataFrame(columns=["code", "date", "price"])
    
    price_column = "open" if use_open else "close"
    
    # IN句で一括取得
    codes_str = ",".join("?" * len(codes))
    dates_str = ",".join("?" * len(dates))
    
    price_df = pd.read_sql_query(
        f"""
        SELECT code, date, {price_column} AS price
        FROM prices_daily
        WHERE code IN ({codes_str}) AND date IN ({dates_str})
        """,
        conn,
        params=(*codes, *dates),
    )
    
    return price_df


def _get_topix_prices_bulk(
    conn, dates: List[str], use_open: bool = False
) -> pd.DataFrame:
    """
    複数日付のTOPIX価格を一括取得（バルクSQL）
    
    Args:
        conn: データベース接続
        dates: 日付のリスト（YYYY-MM-DD）
        use_open: Trueの場合は始値、Falseの場合は終値を取得
    
    Returns:
        DataFrame (date, price列)
    """
    if not dates:
        return pd.DataFrame(columns=["date", "price"])
    
    price_column = "open" if use_open else "close"
    dates_str = ",".join("?" * len(dates))
    
    price_df = pd.read_sql_query(
        f"""
        SELECT date, {price_column} AS price
        FROM index_daily
        WHERE index_code = ? AND date IN ({dates_str})
        """,
        conn,
        params=(TOPIX_CODE, *dates),
    )
    
    return price_df


def _get_rebalance_dates(conn, start_date: str, end_date: str) -> List[str]:
    """
    リバランス日のリストを取得
    
    Args:
        conn: データベース接続
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
    
    Returns:
        リバランス日のリスト
    """
    df = pd.read_sql_query(
        """
        SELECT DISTINCT rebalance_date
        FROM portfolio_monthly
        WHERE rebalance_date >= ? AND rebalance_date <= ?
        ORDER BY rebalance_date ASC
        """,
        conn,
        params=(start_date, end_date),
    )
    return df["rebalance_date"].tolist()


def _get_portfolio(conn, rebalance_date: str) -> pd.DataFrame:
    """
    指定日のポートフォリオを取得
    
    Args:
        conn: データベース接続
        rebalance_date: リバランス日（YYYY-MM-DD）
    
    Returns:
        ポートフォリオのDataFrame（code, weight列を含む）
    """
    return pd.read_sql_query(
        """
        SELECT code, weight
        FROM portfolio_monthly
        WHERE rebalance_date = ?
        """,
        conn,
        params=(rebalance_date,),
    )


def _calculate_turnover(
    current_portfolio: pd.DataFrame,
    previous_portfolio: Optional[pd.DataFrame],
) -> Dict[str, float]:
    """
    ターンオーバーを計算
    
    【実売買ベースのターンオーバー】
    - 毎回いったん全売却→翌日寄りで買付のため
    - executed_sell_notional = 1.0（毎回100%売る）
    - executed_buy_notional = 1.0（毎回100%買う）
    - executed_turnover = executed_sell_notional + executed_buy_notional = 2.0
    
    【参考値: paper turnover】
    - 等金額なら銘柄入替割合でも可
    - paper_turnover = 0.5 * sum(|w_target - w_prev_drift|)
    
    Args:
        current_portfolio: 現在のポートフォリオ（code, weight列）
        previous_portfolio: 前回のポートフォリオ（code, weight列、Noneの場合は初回）
    
    Returns:
        ターンオーバー情報の辞書:
        - executed_sell_notional: 実売却額（1.0 = 100%）
        - executed_buy_notional: 実購入額（1.0 = 100%）
        - executed_turnover: 実ターンオーバー（2.0 = 200%）
        - paper_turnover: 参考値（銘柄入替割合、0.0-1.0）
    """
    # 実売買ベースのターンオーバー（毎回100%売って100%買う）
    executed_sell_notional = 1.0
    executed_buy_notional = 1.0
    executed_turnover = executed_sell_notional + executed_buy_notional  # 2.0
    
    # 参考値: paper turnover（銘柄入替割合）
    if previous_portfolio is None or previous_portfolio.empty:
        paper_turnover = 1.0  # 初回は100%入替
    else:
        # 現在のポートフォリオの銘柄セット
        current_codes = set(current_portfolio["code"].tolist())
        previous_codes = set(previous_portfolio["code"].tolist())
        
        # 入替銘柄の割合（簡易版: 等金額の場合）
        new_codes = current_codes - previous_codes
        removed_codes = previous_codes - current_codes
        paper_turnover = (len(new_codes) + len(removed_codes)) / (2.0 * max(len(current_codes), 1))
        paper_turnover = min(1.0, paper_turnover)
    
    return {
        "executed_sell_notional": executed_sell_notional,
        "executed_buy_notional": executed_buy_notional,
        "executed_turnover": executed_turnover,
        "paper_turnover": paper_turnover,
    }


def calculate_timeseries_returns_from_portfolios(
    portfolios: Dict[str, pd.DataFrame],
    start_date: str,
    end_date: str,
    rebalance_dates: Optional[List[str]] = None,
    cost_bps: float = 0.0,
    buy_cost_bps: Optional[float] = None,
    sell_cost_bps: Optional[float] = None,
) -> Dict[str, Any]:
    """
    時系列P/Lを計算（ポートフォリオを直接受け取る版）
    
    DBから読み込まず、メモリ上のportfolios辞書を使用します。
    これにより、save_portfolio()の呼び出しを回避し、SQLiteロック待ちを削減できます。
    
    Args:
        portfolios: {rebalance_date: portfolio_df} の辞書
                    portfolio_dfは code, weight 列を含む必要がある
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        rebalance_dates: リバランス日のリスト（Noneの場合はportfoliosのキーから取得）
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        buy_cost_bps: 購入コスト（bps、Noneの場合はcost_bpsを使用）
        sell_cost_bps: 売却コスト（bps、Noneの場合はcost_bpsを使用）
    
    Returns:
        時系列P/L情報の辞書（calculate_timeseries_returnsと同じ形式）
    """
    # リバランス日のリストを取得
    if rebalance_dates is None:
        rebalance_dates = sorted([d for d in portfolios.keys() if start_date <= d <= end_date])
    
    if not rebalance_dates:
        return {
            "monthly_returns": [],
            "monthly_excess_returns": [],
            "equity_curve": [1.0],
            "dates": [],
            "portfolio_details": [],
        }
    
    # 以降は calculate_timeseries_returns と同じロジックだが、
    # _get_portfolio() の代わりに portfolios[rebalance_date] を使用
    monthly_returns = []
    monthly_excess_returns = []
    equity_curve = [1.0]
    portfolio_details = []
    dates_with_data = []  # 実データが存在するリバランス日のみを記録
    missing_periods_info = []  # スキップされた期間の情報を記録
    
    # コストパラメータの設定
    if buy_cost_bps is None:
        buy_cost_bps = cost_bps
    if sell_cost_bps is None:
        sell_cost_bps = cost_bps
    
    previous_portfolio = None
    
    with connect_db() as conn:
        for i, rebalance_date in enumerate(rebalance_dates):
            # 次のリバランス日を取得
            if i + 1 < len(rebalance_dates):
                next_rebalance_date = rebalance_dates[i + 1]
            else:
                next_rebalance_date = end_date
            
            # ポートフォリオを取得（メモリから）
            if rebalance_date not in portfolios:
                # ポートフォリオが存在しない場合はスキップ（実データのみを返すため）
                missing_periods_info.append({
                    "rebalance_date": rebalance_date,
                    "reason": "portfolio_not_found",
                })
                continue
            
            portfolio = portfolios[rebalance_date].copy()
            if portfolio.empty:
                # ポートフォリオが空の場合はスキップ（実データのみを返すため）
                missing_periods_info.append({
                    "rebalance_date": rebalance_date,
                    "reason": "portfolio_empty",
                })
                continue
            
            # リバランス日の翌営業日を取得（購入日）
            purchase_date = _get_next_trading_day(conn, rebalance_date)
            if purchase_date is None:
                # 購入日が取得できない場合はスキップ（実データのみを返すため）
                missing_periods_info.append({
                    "rebalance_date": rebalance_date,
                    "reason": "purchase_date_not_found",
                })
                continue
            
            # 売却日は次のリバランス日（終値で売却）
            sell_date = next_rebalance_date
            
            # 各銘柄のリターンを計算（バルク取得+ベクトル計算）
            # 必要な価格を一括取得
            codes = portfolio["code"].tolist()
            purchase_prices_df = _get_prices_bulk(conn, codes, [purchase_date], use_open=True)
            sell_prices_df = _get_prices_bulk(conn, codes, [sell_date], use_open=False)
            
            # DataFrameにマージ
            portfolio_with_prices = portfolio.copy()
            purchase_prices_df = purchase_prices_df.rename(columns={"price": "purchase_price"})
            sell_prices_df = sell_prices_df.rename(columns={"price": "sell_price"})
            
            portfolio_with_prices = portfolio_with_prices.merge(
                purchase_prices_df[["code", "purchase_price"]], on="code", how="left"
            )
            portfolio_with_prices = portfolio_with_prices.merge(
                sell_prices_df[["code", "sell_price"]], on="code", how="left"
            )
            
            # 欠損銘柄を除外
            missing_mask = (
                portfolio_with_prices["purchase_price"].isna() |
                portfolio_with_prices["sell_price"].isna()
            )
            missing_codes = portfolio_with_prices[missing_mask]["code"].tolist()
            portfolio_valid = portfolio_with_prices[~missing_mask].copy()
            
            if portfolio_valid.empty:
                stock_returns = []
            else:
                # 株式分割を考慮（ベクトル計算）
                # 注意: _split_multiplier_betweenは個別呼び出しが必要だが、
                # 将来的にはバルク化できる可能性がある
                split_mults = []
                for code in portfolio_valid["code"]:
                    split_mult = _split_multiplier_between(conn, code, purchase_date, sell_date)
                    split_mults.append(split_mult)
                portfolio_valid["split_mult"] = split_mults
                
                # リターン計算（ベクトル化）
                portfolio_valid["adjusted_purchase_price"] = (
                    portfolio_valid["purchase_price"] / portfolio_valid["split_mult"]
                )
                portfolio_valid["return_decimal"] = (
                    portfolio_valid["sell_price"] / portfolio_valid["adjusted_purchase_price"] - 1.0
                )
                
                # stock_returns形式に変換
                stock_returns = [
                    {
                        "code": row["code"],
                        "weight": row["weight"],
                        "return_decimal": row["return_decimal"],
                    }
                    for _, row in portfolio_valid.iterrows()
                ]
            
            # ポートフォリオ全体のグロスリターン（重み付き平均）
            if stock_returns:
                total_weight = sum(r["weight"] for r in stock_returns)
                if total_weight > 0:
                    for r in stock_returns:
                        r["weight"] = r["weight"] / total_weight
                    
                    portfolio_return_gross = sum(
                        r["weight"] * r["return_decimal"] 
                        for r in stock_returns
                    )
                else:
                    portfolio_return_gross = 0.0
                
                # ターンオーバーを計算
                turnover_info = _calculate_turnover(portfolio, previous_portfolio)
                executed_sell_notional = turnover_info["executed_sell_notional"]
                executed_buy_notional = turnover_info["executed_buy_notional"]
                executed_turnover = turnover_info["executed_turnover"]
                paper_turnover = turnover_info["paper_turnover"]
                
                # 取引コストを控除
                cost_frac = (
                    executed_buy_notional * buy_cost_bps / 1e4
                    + executed_sell_notional * sell_cost_bps / 1e4
                )
                portfolio_return_net = portfolio_return_gross - cost_frac
                
                # TOPIXリターンを計算（バルク取得を使用）
                topix_prices_df = _get_topix_prices_bulk(conn, [purchase_date, sell_date], use_open=False)
                topix_purchase_df = _get_topix_prices_bulk(conn, [purchase_date], use_open=True)
                
                topix_purchase = None
                topix_sell = None
                if not topix_purchase_df.empty and purchase_date in topix_purchase_df["date"].values:
                    topix_purchase = float(topix_purchase_df[topix_purchase_df["date"] == purchase_date]["price"].iloc[0])
                if not topix_prices_df.empty and sell_date in topix_prices_df["date"].values:
                    topix_sell = float(topix_prices_df[topix_prices_df["date"] == sell_date]["price"].iloc[0])
                
                if topix_purchase is not None and topix_sell is not None and topix_purchase > 0:
                    topix_return = (topix_sell / topix_purchase - 1.0)
                    excess_return = portfolio_return_net - topix_return
                else:
                    topix_return = 0.0
                    excess_return = portfolio_return_net
                
                monthly_returns.append(portfolio_return_net)
                monthly_excess_returns.append(excess_return)
                equity_curve.append(equity_curve[-1] * (1.0 + portfolio_return_net))
                dates_with_data.append(rebalance_date)  # 実データが追加された時だけdatesにも追加
                
                portfolio_details.append({
                    "rebalance_date": rebalance_date,
                    "purchase_date": purchase_date,
                    "sell_date": sell_date,
                    "next_rebalance_date": next_rebalance_date,
                    "num_stocks": len(stock_returns),
                    "num_missing_stocks": len(missing_codes),
                    "missing_codes": missing_codes[:10],
                    "portfolio_return_gross": portfolio_return_gross,
                    "portfolio_return_net": portfolio_return_net,
                    "topix_return": topix_return,
                    "excess_return": excess_return,
                    "executed_sell_notional": executed_sell_notional,
                    "executed_buy_notional": executed_buy_notional,
                    "executed_turnover": executed_turnover,
                    "paper_turnover": paper_turnover,
                    "cost_frac": cost_frac,
                })
                
                previous_portfolio = portfolio.copy()
                
                if missing_codes:
                    print(
                        f"警告: {rebalance_date} で {len(missing_codes)}銘柄の価格データが欠損しています。"
                        f"（銘柄コード: {missing_codes[:5]}{'...' if len(missing_codes) > 5 else ''}）"
                    )
            else:
                # portfolio_valid.emptyの場合、データが取得できないためスキップ（0.0を追加しない）
                missing_periods_info.append({
                    "rebalance_date": rebalance_date,
                    "reason": "no_valid_stocks",
                    "purchase_date": purchase_date,
                    "sell_date": sell_date,
                })
    
    return {
        "monthly_returns": monthly_returns,
        "monthly_excess_returns": monthly_excess_returns,
        "equity_curve": equity_curve,
        "dates": dates_with_data,  # 実データが存在するリバランス日のみを返す
        "portfolio_details": portfolio_details,
        "missing_periods_count": len(missing_periods_info),  # スキップされた期間数
        "missing_periods_info": missing_periods_info,  # スキップされた期間の詳細情報
    }


def calculate_timeseries_returns(
    start_date: str,
    end_date: str,
    rebalance_dates: Optional[List[str]] = None,
    cost_bps: float = 0.0,
    buy_cost_bps: Optional[float] = None,
    sell_cost_bps: Optional[float] = None,
) -> Dict[str, Any]:
    """
    時系列P/Lを計算
    
    各リバランス日 ti から次のリバランス日 ti+1 までの月次リターンを計算します。
    
    【売買タイミング: open-close方式】
    - 意思決定: リバランス日 t の引けでシグナル確定（tまでの情報で計算）
    - 購入執行: 翌営業日 t+1 の寄り成（open）で購入
    - 売却執行: 次のリバランス日 t_next の引け成（close）で売却
    - リターン: open(t+1) → close(t_next) の期間
    - TOPIXも同じタイミングで統一（購入: open、売却: close）
    
    【欠損銘柄のウェイト設計: drop_and_renormalize】
    - 価格データが欠損した銘柄は除外
    - 残り銘柄でウェイトを再正規化（常にフルインベスト）
    - 欠損銘柄の情報は portfolio_details に記録
    
    【価格取得: 完全一致】
    - 指定日の価格データが存在しない場合はNoneを返す
    - 欠損時はその銘柄を当月の取引から除外
    
    【取引コスト: ターンオーバー連動】
    - 毎回100%売って100%買うため、executed_turnover = 2.0
    - コスト（bps）を buy/sell で分け、期間リターンから控除
    - cost_frac = executed_buy_notional * buy_cost_bps/10000 + executed_sell_notional * sell_cost_bps/10000
    - r_net = r_gross - cost_frac
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        rebalance_dates: リバランス日のリスト（Noneの場合は自動取得）
        cost_bps: 取引コスト（bps、デフォルト: 0.0、buy_cost_bps/sell_cost_bpsが指定されていない場合に使用）
        buy_cost_bps: 購入コスト（bps、Noneの場合はcost_bpsを使用）
        sell_cost_bps: 売却コスト（bps、Noneの場合はcost_bpsを使用）
    
    Returns:
        時系列P/L情報の辞書:
        - monthly_returns: 月次リターンのリスト（小数、0.01 = 1%）
        - monthly_excess_returns: 月次超過リターンのリスト（小数）
        - equity_curve: エクイティカーブ（初期値1.0）
        - dates: リバランス日のリスト
        - portfolio_details: 各リバランス日のポートフォリオ詳細
    """
    with connect_db() as conn:
        # リバランス日のリストを取得
        if rebalance_dates is None:
            rebalance_dates = _get_rebalance_dates(conn, start_date, end_date)
        
        if not rebalance_dates:
            return {
                "monthly_returns": [],
                "monthly_excess_returns": [],
                "equity_curve": [1.0],
                "dates": [],
                "portfolio_details": [],
            }
        
        monthly_returns = []
        monthly_excess_returns = []
        equity_curve = [1.0]  # 初期値1.0
        portfolio_details = []
        
        # コストパラメータの設定
        if buy_cost_bps is None:
            buy_cost_bps = cost_bps
        if sell_cost_bps is None:
            sell_cost_bps = cost_bps
        
        previous_portfolio = None  # 前回のポートフォリオ（ターンオーバー計算用）
        
        for i, rebalance_date in enumerate(rebalance_dates):
            # 次のリバランス日を取得（最後の場合はend_date）
            if i + 1 < len(rebalance_dates):
                next_rebalance_date = rebalance_dates[i + 1]
            else:
                next_rebalance_date = end_date
            
            # ポートフォリオを取得
            portfolio = _get_portfolio(conn, rebalance_date)
            if portfolio.empty:
                monthly_returns.append(0.0)
                monthly_excess_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
                continue
            
            # 【売買タイミング: open-close方式】
            # 意思決定: リバランス日 t の引けでシグナル確定（tまでの情報で計算）
            # 購入執行: 翌営業日 t+1 の寄り成（open）で購入
            # 売却執行: 次のリバランス日 t_next の引け成（close）で売却
            # リターン: open(t+1) → close(t_next) の期間
            
            # リバランス日の翌営業日を取得（購入日）
            purchase_date = _get_next_trading_day(conn, rebalance_date)
            if purchase_date is None:
                monthly_returns.append(0.0)
                monthly_excess_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
                continue
            
            # 売却日は次のリバランス日（終値で売却）
            sell_date = next_rebalance_date
            
            # 各銘柄のリターンを計算（バルク取得+ベクトル計算）
            codes = portfolio["code"].tolist()
            purchase_prices_df = _get_prices_bulk(conn, codes, [purchase_date], use_open=True)
            sell_prices_df = _get_prices_bulk(conn, codes, [sell_date], use_open=False)
            
            # DataFrameにマージ
            portfolio_with_prices = portfolio.copy()
            purchase_prices_df = purchase_prices_df.rename(columns={"price": "purchase_price"})
            sell_prices_df = sell_prices_df.rename(columns={"price": "sell_price"})
            
            portfolio_with_prices = portfolio_with_prices.merge(
                purchase_prices_df[["code", "purchase_price"]], on="code", how="left"
            )
            portfolio_with_prices = portfolio_with_prices.merge(
                sell_prices_df[["code", "sell_price"]], on="code", how="left"
            )
            
            # 欠損銘柄を除外
            missing_mask = (
                portfolio_with_prices["purchase_price"].isna() |
                portfolio_with_prices["sell_price"].isna()
            )
            missing_codes = portfolio_with_prices[missing_mask]["code"].tolist()
            portfolio_valid = portfolio_with_prices[~missing_mask].copy()
            
            if portfolio_valid.empty:
                stock_returns = []
            else:
                # 株式分割を考慮（ベクトル計算）
                split_mults = []
                for code in portfolio_valid["code"]:
                    split_mult = _split_multiplier_between(conn, code, purchase_date, sell_date)
                    split_mults.append(split_mult)
                portfolio_valid["split_mult"] = split_mults
                
                # リターン計算（ベクトル化）
                portfolio_valid["adjusted_purchase_price"] = (
                    portfolio_valid["purchase_price"] / portfolio_valid["split_mult"]
                )
                portfolio_valid["return_decimal"] = (
                    portfolio_valid["sell_price"] / portfolio_valid["adjusted_purchase_price"] - 1.0
                )
                
                # stock_returns形式に変換
                stock_returns = [
                    {
                        "code": row["code"],
                        "weight": row["weight"],
                        "return_decimal": row["return_decimal"],
                    }
                    for _, row in portfolio_valid.iterrows()
                ]
            
            # ポートフォリオ全体のグロスリターン（重み付き平均）
            # 【欠損銘柄のウェイト設計: drop_and_renormalize】
            # 欠損銘柄は除外し、残り銘柄でウェイトを再正規化（常にフルインベスト）
            if stock_returns:
                # ウェイトを再正規化（欠損銘柄を除外した分を補正）
                total_weight = sum(r["weight"] for r in stock_returns)
                if total_weight > 0:
                    # 再正規化
                    for r in stock_returns:
                        r["weight"] = r["weight"] / total_weight
                    
                    portfolio_return_gross = sum(
                        r["weight"] * r["return_decimal"] 
                        for r in stock_returns
                    )
                else:
                    portfolio_return_gross = 0.0
                
                # ターンオーバーを計算
                turnover_info = _calculate_turnover(portfolio, previous_portfolio)
                executed_sell_notional = turnover_info["executed_sell_notional"]
                executed_buy_notional = turnover_info["executed_buy_notional"]
                executed_turnover = turnover_info["executed_turnover"]
                paper_turnover = turnover_info["paper_turnover"]
                
                # 取引コストを控除（ターンオーバー連動）
                # cost_frac = executed_buy_notional * buy_cost_bps/10000 + executed_sell_notional * sell_cost_bps/10000
                cost_frac = (
                    executed_buy_notional * buy_cost_bps / 1e4
                    + executed_sell_notional * sell_cost_bps / 1e4
                )
                portfolio_return_net = portfolio_return_gross - cost_frac
                
                # TOPIXリターンを計算（open-close方式で統一）
                # 購入: リバランス日の翌営業日の始値
                # 売却: 次のリバランス日の終値
                # バルク取得を使用（将来的には全期間を一括取得できるが、現状は1回ずつ）
                topix_prices_df = _get_topix_prices_bulk(conn, [purchase_date, sell_date], use_open=False)
                topix_purchase_df = _get_topix_prices_bulk(conn, [purchase_date], use_open=True)
                
                topix_purchase = None
                topix_sell = None
                if not topix_purchase_df.empty and purchase_date in topix_purchase_df["date"].values:
                    topix_purchase = float(topix_purchase_df[topix_purchase_df["date"] == purchase_date]["price"].iloc[0])
                if not topix_prices_df.empty and sell_date in topix_prices_df["date"].values:
                    topix_sell = float(topix_prices_df[topix_prices_df["date"] == sell_date]["price"].iloc[0])
                
                if topix_purchase is not None and topix_sell is not None and topix_purchase > 0:
                    topix_return = (topix_sell / topix_purchase - 1.0)
                    excess_return = portfolio_return_net - topix_return
                else:
                    topix_return = 0.0
                    excess_return = portfolio_return_net
                
                monthly_returns.append(portfolio_return_net)
                monthly_excess_returns.append(excess_return)
                equity_curve.append(equity_curve[-1] * (1.0 + portfolio_return_net))
                
                portfolio_details.append({
                    "rebalance_date": rebalance_date,
                    "purchase_date": purchase_date,  # リバランス日の翌営業日
                    "sell_date": sell_date,  # 次のリバランス日
                    "next_rebalance_date": next_rebalance_date,
                    "num_stocks": len(stock_returns),
                    "num_missing_stocks": len(missing_codes),  # 欠損銘柄数
                    "missing_codes": missing_codes[:10],  # 欠損銘柄コード（最大10件）
                    "portfolio_return_gross": portfolio_return_gross,
                    "portfolio_return_net": portfolio_return_net,
                    "topix_return": topix_return,
                    "excess_return": excess_return,
                    "executed_sell_notional": executed_sell_notional,
                    "executed_buy_notional": executed_buy_notional,
                    "executed_turnover": executed_turnover,
                    "paper_turnover": paper_turnover,
                    "cost_frac": cost_frac,
                })
                
                # 前回のポートフォリオを更新（ターンオーバー計算用）
                previous_portfolio = portfolio.copy()
                
                # 欠損銘柄がある場合は警告ログ
                if missing_codes:
                    print(
                        f"警告: {rebalance_date} で {len(missing_codes)}銘柄の価格データが欠損しています。"
                        f"（銘柄コード: {missing_codes[:5]}{'...' if len(missing_codes) > 5 else ''}）"
                    )
            else:
                monthly_returns.append(0.0)
                monthly_excess_returns.append(0.0)
                equity_curve.append(equity_curve[-1])
        
        return {
            "monthly_returns": monthly_returns,  # 小数（0.01 = 1%）
            "monthly_excess_returns": monthly_excess_returns,  # 小数
            "equity_curve": equity_curve,  # 初期値1.0からの累積
            "dates": rebalance_dates,
            "portfolio_details": portfolio_details,
        }

