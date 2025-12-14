"""月次実行ジョブ（特徴量計算 → スコアリング → ポートフォリオ選定）"""

from datetime import datetime
from typing import Optional

from ..infra.db import connect_db, upsert
from ..config.settings import EXECUTION_DATE
from ..config.strategy import StrategyConfig, default_strategy
from ..features.fundamentals import calculate_roe, calculate_roe_trend, check_record_high, calculate_growth_rate
from ..features.valuation import calculate_per, calculate_pbr, calculate_forward_per
from ..features.universe import calculate_liquidity_60d, estimate_market_cap, is_prime_market
from ..strategy.scoring import calculate_core_score, calculate_entry_score
from ..strategy.select import select_portfolio, apply_replacement_limit


def calculate_all_features(as_of_date: str):
    """
    全銘柄の特徴量を計算して保存
    
    Args:
        as_of_date: 基準日（YYYY-MM-DD）
    """
    print(f"特徴量を計算中（基準日: {as_of_date}）...")
    
    with connect_db() as conn:
        # 全銘柄コードを取得
        sql = """
            SELECT DISTINCT code
            FROM listed_info
            WHERE date = (
                SELECT MAX(date) FROM listed_info WHERE date <= ?
            )
        """
        codes = [row["code"] for row in conn.execute(sql, (as_of_date,)).fetchall()]
        
        features = []
        
        for code in codes:
            try:
                # 基本情報
                liquidity_60d = calculate_liquidity_60d(conn, code, as_of_date)
                market_cap = estimate_market_cap(conn, code, as_of_date)
                
                # 業種
                sql = """
                    SELECT sector33
                    FROM listed_info
                    WHERE code = ? AND date = (
                        SELECT MAX(date) FROM listed_info WHERE code = ? AND date <= ?
                    )
                """
                row = conn.execute(sql, (code, code, as_of_date)).fetchone()
                sector33 = row["sector33"] if row else None
                
                # 財務指標
                sql = """
                    SELECT profit, equity, eps, bvps, forecast_eps,
                           operating_profit, forecast_operating_profit,
                           forecast_profit, current_period_end
                    FROM fins_statements
                    WHERE code = ? AND type_of_current_period = 'FY'
                    ORDER BY current_period_end DESC
                    LIMIT 2
                """
                rows = conn.execute(sql, (code,)).fetchall()
                
                if not rows:
                    continue
                
                latest = rows[0]
                
                # 株価
                sql = """
                    SELECT adj_close
                    FROM prices_daily
                    WHERE code = ? AND date <= ?
                    ORDER BY date DESC
                    LIMIT 1
                """
                price_row = conn.execute(sql, (code, as_of_date)).fetchone()
                if not price_row or price_row["adj_close"] is None:
                    continue
                
                price = price_row["adj_close"]
                
                # 計算
                roe = calculate_roe(latest["profit"], latest["equity"])
                roe_trend = calculate_roe_trend(conn, code, latest["current_period_end"]) if latest["current_period_end"] else None
                per = calculate_per(price, latest["eps"])
                pbr = calculate_pbr(price, latest["bvps"])
                forward_per = calculate_forward_per(price, latest["forecast_eps"])
                
                # 成長率
                op_growth = None
                profit_growth = None
                if len(rows) >= 2:
                    previous = rows[1]
                    op_growth = calculate_growth_rate(
                        latest["operating_profit"],
                        previous["operating_profit"],
                    )
                    profit_growth = calculate_growth_rate(
                        latest["profit"],
                        previous["profit"],
                    )
                elif latest["forecast_operating_profit"] and latest["operating_profit"]:
                    op_growth = calculate_growth_rate(
                        latest["forecast_operating_profit"],
                        latest["operating_profit"],
                    )
                elif latest["forecast_profit"] and latest["profit"]:
                    profit_growth = calculate_growth_rate(
                        latest["forecast_profit"],
                        latest["profit"],
                    )
                
                # 最高益フラグ
                record_high_flag, record_high_forecast_flag = (
                    check_record_high(conn, code, latest["current_period_end"])
                    if latest["current_period_end"] else (False, False)
                )
                
                # スコアリング
                core_score = calculate_core_score(conn, code, as_of_date)
                entry_score = calculate_entry_score(conn, code, as_of_date)
                
                features.append({
                    "as_of_date": as_of_date,
                    "code": code,
                    "sector33": sector33,
                    "liquidity_60d": liquidity_60d,
                    "market_cap": market_cap,
                    "roe": roe,
                    "roe_trend": roe_trend,
                    "per": per,
                    "pbr": pbr,
                    "forward_per": forward_per,
                    "op_growth": op_growth,
                    "profit_growth": profit_growth,
                    "record_high_flag": 1 if record_high_flag else 0,
                    "record_high_forecast_flag": 1 if record_high_forecast_flag else 0,
                    "core_score": core_score,
                    "entry_score": entry_score,
                })
            except Exception as e:
                print(f"エラー（銘柄コード {code}）: {e}")
                continue
        
        # 保存
        upsert(conn, "features_monthly", features, conflict_columns=["as_of_date", "code"])
        print(f"特徴量の計算が完了しました（{len(features)}銘柄）")


def run_monthly_rebalance(
    as_of_date: str,
    previous_date: Optional[str] = None,
    config: StrategyConfig = default_strategy,
):
    """
    月次リバランスを実行
    
    Args:
        as_of_date: リバランス日（YYYY-MM-DD）
        previous_date: 前回リバランス日（Noneの場合は自動検出）
        config: 戦略設定
    """
    print(f"月次リバランスを実行中（日付: {as_of_date}）...")
    
    with connect_db() as conn:
        # 前回リバランス日を取得
        if previous_date is None:
            sql = """
                SELECT MAX(rebalance_date) as max_date
                FROM portfolio_monthly
            """
            row = conn.execute(sql).fetchone()
            previous_date = row["max_date"] if row and row["max_date"] else None
        
        # 特徴量を計算
        calculate_all_features(as_of_date)
        
        # ポートフォリオを選定
        portfolio = select_portfolio(conn, as_of_date, config)
        
        # 入替上限を適用
        if previous_date:
            portfolio = apply_replacement_limit(conn, portfolio, previous_date, config)
        
        # 保存
        portfolio_data = [
            {
                "rebalance_date": as_of_date,
                "code": item["code"],
                "weight": item["weight"],
                "core_score": item["core_score"],
                "entry_score": item["entry_score"],
                "reason": item["reason"],
            }
            for item in portfolio
        ]
        
        upsert(conn, "portfolio_monthly", portfolio_data, conflict_columns=["rebalance_date", "code"])
        
        print(f"リバランスが完了しました（{len(portfolio)}銘柄）")


def main(
    date: Optional[str] = None,
    config: Optional[StrategyConfig] = None,
):
    """
    月次実行ジョブのメイン関数
    
    Args:
        date: 実行日（YYYY-MM-DD、Noneの場合は今日）
        config: 戦略設定（Noneの場合はデフォルト）
    """
    if date is None:
        date = EXECUTION_DATE or datetime.now().strftime("%Y-%m-%d")
    
    if config is None:
        config = default_strategy
    
    run_monthly_rebalance(date, config=config)


if __name__ == "__main__":
    main()


