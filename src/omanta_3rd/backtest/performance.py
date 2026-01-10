"""ポートフォリオのパフォーマンス計算"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime
import sqlite3
import pandas as pd

from ..infra.db import connect_db, upsert
from ..ingest.indices import TOPIX_CODE


def _get_next_trading_day(conn, date: str, max_date: Optional[str] = None) -> Optional[str]:
    """
    指定日付の翌営業日を取得（価格データが存在する最初の営業日）
    
    重要: 日本の株式市場は月〜金が営業日（weekday 0-4）です。
          データベースに非営業日のデータが含まれている場合でも、
          実際の営業日（月〜金）のみを返します。
    
    さらに、価格データ（openまたはclose）がNULLでない日付のみを返します。
    これは、データベースにレコードが存在しても価格データがNULLの場合があるためです。
    
    Args:
        conn: データベース接続
        date: 基準日（YYYY-MM-DD）
        max_date: 最大日付（YYYY-MM-DD、Noneの場合は制限なし）
                  データリーク防止のため、リバランス日以前のデータのみを参照
    
    Returns:
        翌営業日（YYYY-MM-DD）、存在しない場合はNone
    """
    from datetime import datetime
    
    # データベースから、基準日より後の日付で、価格データ（openまたはclose）がNULLでない日付を取得
    # 最大7日分を確認
    # 重要: max_dateが指定されている場合、max_date以前のデータのみを参照（データリーク防止）
    if max_date is not None:
        next_dates_df = pd.read_sql_query(
            """
            SELECT DISTINCT date
            FROM prices_daily
            WHERE date > ?
              AND date <= ?
              AND (open IS NOT NULL OR close IS NOT NULL)
            ORDER BY date
            LIMIT 7
            """,
            conn,
            params=(date, max_date),
        )
    else:
        next_dates_df = pd.read_sql_query(
            """
            SELECT DISTINCT date
            FROM prices_daily
            WHERE date > ?
              AND (open IS NOT NULL OR close IS NOT NULL)
            ORDER BY date
            LIMIT 7
            """,
            conn,
            params=(date,),
        )
    
    if next_dates_df.empty:
        return None
    
    # 実際の営業日（月〜金、weekday 0-4）を探す
    for _, row in next_dates_df.iterrows():
        candidate_date = str(row["date"])
        dt = datetime.strptime(candidate_date, "%Y-%m-%d")
        weekday = dt.weekday()  # 0=月曜日, 4=金曜日, 5=土曜日, 6=日曜日
        
        # 月〜金（weekday 0-4）が営業日
        if weekday < 5:
            return candidate_date
    
    # 7日以内に営業日が見つからない場合（通常は発生しない）
    # 最初の日付を返す（フォールバック）
    return str(next_dates_df.iloc[0]["date"])


def _get_topix_price(conn, date: str, use_open: bool = False) -> Optional[float]:
    """
    指定日のTOPIX価格を取得
    
    Args:
        conn: データベース接続
        date: 日付（YYYY-MM-DD）
        use_open: Trueの場合は始値、Falseの場合は終値を取得（デフォルト: False）
    
    Returns:
        TOPIX価格（始値または終値）、存在しない場合はNone
    """
    price_column = "open" if use_open else "close"
    price_df = pd.read_sql_query(
        f"""
        SELECT {price_column}
        FROM index_daily
        WHERE index_code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 1
        """,
        conn,
        params=(TOPIX_CODE, date),
    )
    
    if price_df.empty or pd.isna(price_df[price_column].iloc[0]):
        return None
    
    return float(price_df[price_column].iloc[0])


def _split_multiplier_between(conn, code: str, start_date: str, end_date: str) -> float:
    """
    指定期間内の分割・併合による株数倍率を計算
    
    (start_date, end_date] の期間に発生したAdjustmentFactorから、
    株数倍率 = ∏(1 / adjustment_factor) を計算します。
    
    例: 1:3分割（adjustment_factor = 0.333333）の場合、
    株数倍率 = 1 / 0.333333 ≈ 3.0
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        start_date: 開始日（YYYY-MM-DD、通常は購入日の翌営業日）
        end_date: 終了日（YYYY-MM-DD、評価日）
    
    Returns:
        株数倍率（分割・併合がない場合は1.0）
    """
    # start_dateより後、end_date以下のAdjustmentFactorを取得
    df = pd.read_sql_query(
        """
        SELECT date, adjustment_factor
        FROM prices_daily
        WHERE code = ?
          AND date > ?
          AND date <= ?
          AND adjustment_factor IS NOT NULL
          AND adjustment_factor != 1.0
        ORDER BY date ASC
        """,
        conn,
        params=(code, start_date, end_date),
    )
    
    if df.empty:
        return 1.0
    
    # 株数倍率を計算: split_mult = ∏(1 / adjustment_factor)
    mult = 1.0
    invalid_factors = []
    for _, row in df.iterrows():
        adj_factor = row["adjustment_factor"]
        split_date = row["date"]
        
        # 不正値の検出と警告
        if pd.isna(adj_factor):
            invalid_factors.append((split_date, "NULL"))
            continue
        
        if adj_factor <= 0:
            # 0や負の値はデータ不正（通常の分割データではあり得ない）
            invalid_factors.append((split_date, f"invalid_value={adj_factor}"))
            # 警告を出力（本番環境ではログに記録）
            print(f"警告: 銘柄{code}の分割データに不正値があります。日付={split_date}, adjustment_factor={adj_factor}")
            continue
        
        mult *= (1.0 / float(adj_factor))
    
    # 不正値があった場合は警告（ただし計算は続行）
    if invalid_factors:
        print(f"警告: 銘柄{code}で{len(invalid_factors)}件の不正なadjustment_factorを検出しました。無視して計算を続行します。")
    
    return mult


def calculate_portfolio_performance(
    rebalance_date: str,
    as_of_date: Optional[str] = None,
    portfolio_table: str = "portfolio_monthly",
) -> Dict[str, Any]:
    """
    指定されたrebalance_dateのポートフォリオのパフォーマンスを計算
    
    Args:
        rebalance_date: リバランス日（YYYY-MM-DD）
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）
        portfolio_table: ポートフォリオテーブル名（デフォルト: "portfolio_monthly"）
                         長期保有型: "portfolio_monthly"
                         月次リバランス型: "monthly_rebalance_portfolio"
        
    Returns:
        パフォーマンス情報の辞書
    """
    with connect_db() as conn:
        # ポートフォリオを取得
        portfolio = pd.read_sql_query(
            f"""
            SELECT code, weight, core_score, entry_score
            FROM {portfolio_table}
            WHERE rebalance_date = ?
            """,
            conn,
            params=(rebalance_date,),
        )
        
        if portfolio.empty:
            return {
                "rebalance_date": rebalance_date,
                "as_of_date": as_of_date,
                "error": "ポートフォリオが見つかりません",
            }
        
        # 評価日を決定（必須）
        # 重要: データリークを防ぐため、as_of_dateは必須とする
        #       DB MAX(date)は使用しない（未来参照リーク防止）
        if as_of_date is None:
            return {
                "rebalance_date": rebalance_date,
                "as_of_date": None,
                "error": "as_of_dateは必須です。データリークを防ぐため、リバランス日以前の日付を明示的に指定してください。",
            }
        
        # 型チェック: as_of_dateが文字列であることを保証（SQLクエリで使用するため）
        if not isinstance(as_of_date, str):
            as_of_date = str(as_of_date)
        
        # リバランス日の翌営業日を取得
        # 重要: as_of_date以前のデータのみを参照（データリーク防止）
        next_trading_day = _get_next_trading_day(conn, rebalance_date, max_date=as_of_date)
        if next_trading_day is None:
            return {
                "rebalance_date": rebalance_date,
                "as_of_date": as_of_date,
                "error": f"リバランス日の翌営業日が見つかりません: {rebalance_date} (as_of_date={as_of_date}以前のデータを参照)",
            }
        
        # 各銘柄のリバランス日の翌営業日の始値を取得（購入価格）
        # 注意: 購入価格が取得できない銘柄はrebalance_priceがNaNになり、
        #       後続のreturn_pct計算でNaNになる（欠損値として扱われる）
        # 重要: 始値（open）がNULLの場合は終値（close）をフォールバックとして使用
        rebalance_prices = []
        missing_buy_prices = []
        for code in portfolio["code"]:
            price_row = pd.read_sql_query(
                """
                SELECT open, close
                FROM prices_daily
                WHERE code = ? AND date = ?
                """,
                conn,
                params=(code, next_trading_day),
            )
            if not price_row.empty:
                # 始値がNULLの場合は終値をフォールバックとして使用
                buy_price = price_row["open"].iloc[0]
                if buy_price is None or pd.isna(buy_price):
                    buy_price = price_row["close"].iloc[0]
                
                if buy_price is not None and not pd.isna(buy_price):
                    rebalance_prices.append({
                        "code": code,
                        "rebalance_price": buy_price,
                    })
                else:
                    missing_buy_prices.append(code)
            else:
                missing_buy_prices.append(code)
        
        if missing_buy_prices:
            print(
                f"警告: {rebalance_date}のリバランスで{len(missing_buy_prices)}銘柄で購入価格が取得できませんでした。"
                f"（銘柄コード: {missing_buy_prices[:5]}{'...' if len(missing_buy_prices) > 5 else ''}, "
                f"翌営業日: {next_trading_day}）"
            )
            # デバッグ用: 翌営業日に価格データがある銘柄の数を確認
            all_codes_count = pd.read_sql_query(
                """
                SELECT COUNT(DISTINCT code) as count
                FROM prices_daily
                WHERE date = ?
                """,
                conn,
                params=(next_trading_day,),
            )
            print(
                f"  デバッグ: 翌営業日 {next_trading_day} に価格データがある全銘柄数: "
                f"{all_codes_count['count'].iloc[0] if not all_codes_count.empty else 0}"
            )
            # ポートフォリオの銘柄が翌営業日に存在するか確認
            portfolio_codes = portfolio["code"].tolist()
            if portfolio_codes:
                portfolio_codes_str = "','".join(portfolio_codes)
                portfolio_codes_count = pd.read_sql_query(
                    f"""
                    SELECT COUNT(DISTINCT code) as count
                    FROM prices_daily
                    WHERE date = ?
                      AND code IN ('{portfolio_codes_str}')
                    """,
                    conn,
                    params=(next_trading_day,),
                )
                print(
                    f"  デバッグ: ポートフォリオの銘柄のうち、翌営業日に価格データがある銘柄数: "
                    f"{portfolio_codes_count['count'].iloc[0] if not portfolio_codes_count.empty else 0}/{len(portfolio_codes)}"
                )
                # データが存在しない銘柄のリストも表示
                missing_codes_in_db = []
                for code in portfolio_codes:
                    code_check = pd.read_sql_query(
                        "SELECT COUNT(*) as count FROM prices_daily WHERE code = ? AND date = ?",
                        conn,
                        params=(code, next_trading_day),
                    )
                    if code_check.empty or code_check["count"].iloc[0] == 0:
                        missing_codes_in_db.append(code)
                if missing_codes_in_db:
                    print(
                        f"  デバッグ: 翌営業日にデータが存在しない銘柄: {missing_codes_in_db[:10]}{'...' if len(missing_codes_in_db) > 10 else ''}"
                    )
            else:
                print("  デバッグ: ポートフォリオが空です")
        
        # rebalance_pricesが空の場合でも、codeカラムを持つDataFrameを作成
        if rebalance_prices:
            rebalance_prices_df = pd.DataFrame(rebalance_prices)
        else:
            # 空のDataFrameでもcodeカラムを持つようにする
            rebalance_prices_df = pd.DataFrame(columns=["code", "rebalance_price"])
        
        portfolio = portfolio.merge(rebalance_prices_df, on="code", how="left")
        
        # 各銘柄の現在価格を取得（終値を使用）
        # ========================================================================
        # 重要: 評価日が非営業日のときのズレ問題を解決
        # ========================================================================
        # 実際に評価に使った価格の日付（effective_asof_date）を取得し、
        # その日付までで分割を計算することで、価格と分割の基準日を必ず一致させる
        # これにより、休場日にもcorporate action行が立つ実装でも正しく動作する
        # ========================================================================
        current_prices = []
        split_multipliers = []
        missing_sell_prices = []
        for code in portfolio["code"]:
            price_row = pd.read_sql_query(
                """
                SELECT date, close
                FROM prices_daily
                WHERE code = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 1
                """,
                conn,
                params=(code, as_of_date),
            )
            if not price_row.empty and price_row["close"].iloc[0] is not None:
                effective_asof_date = str(price_row["date"].iloc[0])  # 実際に評価に使った価格の日付
                current_prices.append({
                    "code": code,
                    "current_price": price_row["close"].iloc[0],
                })
                # リバランス日の翌営業日以後の分割倍率を計算
                # 重要: effective_asof_dateまでで計算することで、価格と分割の基準日を一致させる
                # これにより、評価日が非営業日でも、価格と分割の基準日が必ず一致する
                split_mult = _split_multiplier_between(conn, code, next_trading_day, effective_asof_date)
                split_multipliers.append({
                    "code": code,
                    "split_multiplier": split_mult,
                })
            else:
                missing_sell_prices.append(code)
        
        if missing_sell_prices:
            print(
                f"警告: {len(missing_sell_prices)}銘柄で評価価格が取得できませんでした。"
                f"（銘柄コード: {missing_sell_prices[:5]}{'...' if len(missing_sell_prices) > 5 else ''}）"
            )
        
        current_prices_df = pd.DataFrame(current_prices)
        portfolio = portfolio.merge(current_prices_df, on="code", how="left")
        
        split_multipliers_df = pd.DataFrame(split_multipliers)
        portfolio = portfolio.merge(split_multipliers_df, on="code", how="left")
        # 分割倍率が取得できなかった場合は1.0とする
        portfolio["split_multiplier"] = portfolio["split_multiplier"].fillna(1.0)
        
        # 損益率を計算（分割を考慮）
        # バックテストでは仮想的な保有なので、価格を調整する方法を使用
        # 分割が発生した場合、購入価格を分割後の基準に調整して比較
        # 例: 1:3分割の場合、購入価格1000円 → 調整後購入価格333.33円
        #     現在価格400円 → リターン = (400 - 333.33) / 333.33 * 100 = 20%
        # 
        # 注意: 実際の保有銘柄では、株数を調整する方法を使用（holdings.pyを参照）
        portfolio["adjusted_current_price"] = portfolio["current_price"] * portfolio["split_multiplier"]
        portfolio["return_pct"] = (
            (portfolio["adjusted_current_price"] - portfolio["rebalance_price"]) 
            / portfolio["rebalance_price"] 
            * 100.0
        )
        
        # ポートフォリオ全体の損益を計算（weightを考慮）
        # ========================================================================
        # 重要: 欠損値の扱いを明示的に処理
        # ========================================================================
        # 欠損値の扱い方針: 方針C（品質管理）
        # - 欠損銘柄（return_pctがNaN）は計算から除外される
        # - 有効銘柄のweight合計（coverage）を計算し、品質指標として返す
        # - 全部NaNの場合はtotal_returnもNaNを返す（sum(min_count=1)を使用）
        # - 呼び出し側でweight_coverageを確認し、品質を判断できる
        # ========================================================================
        
        portfolio["weighted_return"] = portfolio["weight"] * portfolio["return_pct"]
        
        # 有効銘柄（return_pctがNaNでない）のweight合計を計算（coverage）
        valid_mask = portfolio["return_pct"].notna()
        valid_weight_sum = portfolio.loc[valid_mask, "weight"].sum()
        total_weight = portfolio["weight"].sum()
        num_valid = valid_mask.sum()
        num_total = len(portfolio)
        
        if total_weight > 0:
            coverage = valid_weight_sum / total_weight
        else:
            coverage = 0.0
        
        # sum(min_count=1)を使用: 全部NaNならNaNを維持（誤った0%を防ぐ）
        total_return = portfolio["weighted_return"].sum(min_count=1)
        
        # 欠損値の警告（品質管理）
        MIN_COVERAGE = 0.98  # 98%以上のweightが有効でないと警告
        if coverage < MIN_COVERAGE:
            missing_count = num_total - num_valid
            missing_weight = total_weight - valid_weight_sum
            print(
                f"警告: {rebalance_date}のポートフォリオの品質が低い可能性があります。"
                f"欠損銘柄数={missing_count}/{num_total}, "
                f"欠損weight={missing_weight:.4f}/{total_weight:.4f}, "
                f"coverage={coverage:.4f}, "
                f"翌営業日: {next_trading_day}"
            )
        
        # TOPIX比較: 購入日と評価日のTOPIX価格を取得
        # ========================================================================
        # 重要: 個別株と同じタイミングを使用することで、公平な比較を実現
        # ========================================================================
        # 購入: リバランス日の翌営業日の始値（個別株と同様）
        # 売却: as_of_dateの直近営業日の終値（個別株と同様）
        # 注意: _get_topix_priceは個別株と同じく「date <= ? ORDER BY date DESC LIMIT 1」で
        #       直近営業日の価格を取得するため、非営業日・欠損時の挙動が一致している
        # ========================================================================
        topix_buy_price = _get_topix_price(conn, next_trading_day, use_open=True)
        topix_sell_price = _get_topix_price(conn, as_of_date, use_open=False)
        
        # TOPIXリターンの計算
        topix_return_pct = None
        if topix_buy_price is not None and topix_sell_price is not None and topix_buy_price > 0:
            topix_return_pct = (topix_sell_price - topix_buy_price) / topix_buy_price * 100.0
        
        # 仮想的な総投資金額（比較用、実際の投資金額とは無関係）
        # 各銘柄の投資金額は weight × 総投資金額で計算されるため、
        # 総投資金額の値自体は比較結果に影響しない（リターン率は同じ）
        hypothetical_total_investment = 1_000_000.0  # 100万円（比較用の仮想金額）
        
        # 各銘柄のTOPIX比較リターンを計算
        portfolio["investment_amount"] = portfolio["weight"] * hypothetical_total_investment
        portfolio["topix_return_pct"] = topix_return_pct if topix_return_pct is not None else None
        
        # 銘柄別のTOPIX比較情報を追加
        portfolio["topix_comparison"] = portfolio.apply(
            lambda row: {
                "investment_amount": float(row["investment_amount"]) if pd.notna(row["investment_amount"]) else None,
                "topix_return_pct": float(row["topix_return_pct"]) if pd.notna(row["topix_return_pct"]) else None,
                "stock_return_pct": float(row["return_pct"]) if pd.notna(row["return_pct"]) else None,
                "excess_return_pct": (
                    float(row["return_pct"] - row["topix_return_pct"])
                    if pd.notna(row["return_pct"]) and pd.notna(row["topix_return_pct"])
                    else None
                ),
            },
            axis=1
        )
        
        # ポートフォリオ全体のTOPIX比較
        portfolio_topix_comparison = {
            "total_investment": hypothetical_total_investment,
            "portfolio_return_pct": float(total_return) if not pd.isna(total_return) else None,
            "topix_return_pct": float(topix_return_pct) if topix_return_pct is not None else None,
            "excess_return_pct": (
                float(total_return - topix_return_pct)
                if not pd.isna(total_return) and topix_return_pct is not None
                else None
            ),
        }
        
        # 統計情報
        valid_returns = portfolio[portfolio["return_pct"].notna()]["return_pct"]
        
        result = {
            "rebalance_date": rebalance_date,
            "as_of_date": as_of_date,
            "total_return_pct": float(total_return) if not pd.isna(total_return) else None,
            "num_stocks": len(portfolio),
            "num_stocks_with_price": len(portfolio[portfolio["current_price"].notna()]),
            "num_stocks_with_return": len(valid_returns),  # 有効なリターンがある銘柄数
            "weight_coverage": float(coverage) if total_weight > 0 else None,  # 有効weight割合（品質指標）
            "avg_return_pct": float(valid_returns.mean()) if len(valid_returns) > 0 else None,
            "min_return_pct": float(valid_returns.min()) if len(valid_returns) > 0 else None,
            "max_return_pct": float(valid_returns.max()) if len(valid_returns) > 0 else None,
            "topix_comparison": portfolio_topix_comparison,
            "stocks": portfolio[
                ["code", "weight", "rebalance_price", "current_price", "split_multiplier", 
                 "adjusted_current_price", "return_pct", "topix_comparison"]
            ].to_dict("records"),
        }
        
        return result


def calculate_all_portfolios_performance(
    as_of_date: Optional[str] = None,
    portfolio_table: str = "portfolio_monthly",
) -> List[Dict[str, Any]]:
    """
    すべてのポートフォリオのパフォーマンスを計算
    
    Args:
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）
        portfolio_table: ポートフォリオテーブル名（デフォルト: "portfolio_monthly"）
                         長期保有型: "portfolio_monthly"
                         月次リバランス型: "monthly_rebalance_portfolio"
        
    Returns:
        各ポートフォリオのパフォーマンス情報のリスト
    """
    with connect_db() as conn:
        # すべてのrebalance_dateを取得
        rebalance_dates = pd.read_sql_query(
            f"""
            SELECT DISTINCT rebalance_date
            FROM {portfolio_table}
            ORDER BY rebalance_date
            """,
            conn,
        )["rebalance_date"].tolist()
        
        results = []
        for rebalance_date in rebalance_dates:
            perf = calculate_portfolio_performance(rebalance_date, as_of_date, portfolio_table)
            results.append(perf)
        
        return results


def save_performance_to_db(
    performance: Dict[str, Any],
) -> None:
    """
    パフォーマンス結果をデータベースに保存
    
    Args:
        performance: calculate_portfolio_performance()の戻り値
    """
    if "error" in performance:
        return
    
    with connect_db() as conn:
        # ポートフォリオ全体のパフォーマンスを保存
        topix_comp = performance.get("topix_comparison", {})
        perf_row = {
            "rebalance_date": performance["rebalance_date"],
            "as_of_date": performance["as_of_date"],
            "total_return_pct": performance.get("total_return_pct"),
            "num_stocks": performance.get("num_stocks"),
            "num_stocks_with_price": performance.get("num_stocks_with_price"),
            "num_stocks_with_return": performance.get("num_stocks_with_return"),  # 新規追加
            "weight_coverage": performance.get("weight_coverage"),  # 新規追加
            "avg_return_pct": performance.get("avg_return_pct"),
            "min_return_pct": performance.get("min_return_pct"),
            "max_return_pct": performance.get("max_return_pct"),
            "topix_return_pct": topix_comp.get("topix_return_pct"),
            "excess_return_pct": topix_comp.get("excess_return_pct"),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        upsert(conn, "backtest_performance", [perf_row], conflict_columns=["rebalance_date", "as_of_date"])
        
        # 銘柄別のパフォーマンスを保存
        stock_rows = []
        stocks = performance.get("stocks", [])
        if stocks:
            for stock in stocks:
                # codeが存在することを確認
                if "code" in stock:
                    topix_comp_stock = stock.get("topix_comparison", {})
                    stock_rows.append({
                        "rebalance_date": performance["rebalance_date"],
                        "as_of_date": performance["as_of_date"],
                        "code": stock["code"],
                        "weight": stock.get("weight"),
                        "rebalance_price": stock.get("rebalance_price"),
                        "current_price": stock.get("current_price"),
                        "split_multiplier": stock.get("split_multiplier"),
                        "adjusted_current_price": stock.get("adjusted_current_price"),
                        "return_pct": stock.get("return_pct"),
                        "investment_amount": topix_comp_stock.get("investment_amount"),
                        "topix_return_pct": topix_comp_stock.get("topix_return_pct"),
                        "excess_return_pct": topix_comp_stock.get("excess_return_pct"),
                    })
        
        if stock_rows:
            upsert(
                conn,
                "backtest_stock_performance",
                stock_rows,
                conflict_columns=["rebalance_date", "as_of_date", "code"],
            )

