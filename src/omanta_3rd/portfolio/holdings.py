"""実際の保有銘柄の管理"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime
import sqlite3
import pandas as pd

from ..infra.db import connect_db, upsert
from ..ingest.indices import TOPIX_CODE


def add_holding(
    purchase_date: str,
    code: str,
    shares: float,
    purchase_price: float,
) -> Dict[str, Any]:
    """
    保有銘柄を追加
    
    Args:
        purchase_date: 購入日（YYYY-MM-DD）
        code: 銘柄コード
        shares: 株数
        purchase_price: 購入単価
        
    Returns:
        追加された銘柄の情報
    """
    with connect_db() as conn:
        holding = {
            "purchase_date": purchase_date,
            "code": code,
            "shares": shares,
            "purchase_price": purchase_price,
            "current_price": None,
            "unrealized_pnl": None,
            "return_pct": None,
            "sell_date": None,
            "sell_price": None,
            "realized_pnl": None,
            "topix_return_pct": None,
            "excess_return_pct": None,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        # UNIQUE制約があるため、重複チェックはDBが行う
        try:
            upsert(
                conn,
                "holdings",
                [holding],
                conflict_columns=["purchase_date", "code", "shares", "purchase_price"],
            )
            return holding
        except Exception as e:
            raise ValueError(f"保有銘柄の追加に失敗しました: {e}")


def update_holding_performance(
    holding_id: Optional[int] = None,
    as_of_date: Optional[str] = None,
) -> None:
    """
    保有銘柄のパフォーマンスを更新
    
    Args:
        holding_id: 更新する保有銘柄のID（Noneの場合はすべての保有中の銘柄を更新）
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）
    """
    with connect_db() as conn:
        # 評価日を決定
        if as_of_date is None:
            latest_date_df = pd.read_sql_query(
                "SELECT MAX(date) as max_date FROM prices_daily",
                conn
            )
            if latest_date_df.empty or pd.isna(latest_date_df["max_date"].iloc[0]):
                raise ValueError("価格データが見つかりません")
            as_of_date = latest_date_df["max_date"].iloc[0]
        
        # 更新対象の保有銘柄を取得
        if holding_id:
            query = "SELECT * FROM holdings WHERE id = ?"
            params = (holding_id,)
        else:
            # 保有中（sell_date IS NULL）の銘柄のみ更新
            query = "SELECT * FROM holdings WHERE sell_date IS NULL"
            params = ()
        
        holdings_df = pd.read_sql_query(query, conn, params=params)
        
        if holdings_df.empty:
            return
        
        # 各保有銘柄のパフォーマンスを計算
        updated_holdings = []
        for _, holding in holdings_df.iterrows():
            code = holding["code"]
            purchase_date = holding["purchase_date"]
            shares = holding["shares"]
            purchase_price = holding["purchase_price"]
            sell_date = holding.get("sell_date")
            
            # 評価日を決定（売却済みの場合は売却日、保有中の場合はas_of_date）
            eval_date = sell_date if sell_date else as_of_date
            
            # 現在価格を取得
            if sell_date:
                # 売却済み：sell_priceが設定されている場合はそれを使用、なければ売却日の終値を使用
                if holding.get("sell_price") and pd.notna(holding["sell_price"]):
                    current_price = float(holding["sell_price"])
                else:
                    # 売却日の終値を取得
                    price_df = pd.read_sql_query(
                        """
                        SELECT close
                        FROM prices_daily
                        WHERE code = ? AND date <= ?
                        ORDER BY date DESC
                        LIMIT 1
                        """,
                        conn,
                        params=(code, sell_date),
                    )
                    if price_df.empty or pd.isna(price_df["close"].iloc[0]):
                        continue
                    current_price = float(price_df["close"].iloc[0])
            else:
                # 保有中：as_of_dateの終値を取得
                price_df = pd.read_sql_query(
                    """
                    SELECT close
                    FROM prices_daily
                    WHERE code = ? AND date <= ?
                    ORDER BY date DESC
                    LIMIT 1
                    """,
                    conn,
                    params=(code, as_of_date),
                )
                if price_df.empty or pd.isna(price_df["close"].iloc[0]):
                    continue
                current_price = float(price_df["close"].iloc[0])
            
            # 購入価格はユーザーが入力したpurchase_priceを使用（手打ち入力値）
            actual_purchase_price = float(purchase_price)
            
            # リターンと損益を計算
            return_pct = (current_price - actual_purchase_price) / actual_purchase_price * 100.0
            
            if sell_date:
                # 売却済み：実現損益
                realized_pnl = (current_price - actual_purchase_price) * shares
                unrealized_pnl = None
            else:
                # 保有中：含み損益
                unrealized_pnl = (current_price - actual_purchase_price) * shares
                realized_pnl = None
            
            # TOPIXのパフォーマンスを取得（購入日の始値を使用）
            topix_buy_price = _get_topix_price(conn, purchase_date, use_open=True)
            topix_sell_price = _get_topix_price(conn, eval_date, use_open=False)
            
            topix_return_pct = None
            excess_return_pct = None
            if topix_buy_price is not None and topix_sell_price is not None and topix_buy_price > 0:
                topix_return_pct = (topix_sell_price - topix_buy_price) / topix_buy_price * 100.0
                excess_return_pct = return_pct - topix_return_pct
            
            # 更新データを作成
            updated_holding = {
                "id": int(holding["id"]),
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "return_pct": return_pct,
                "realized_pnl": realized_pnl,
                "topix_return_pct": topix_return_pct,
                "excess_return_pct": excess_return_pct,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            
            # sell_dateとsell_priceがある場合は更新
            if sell_date:
                updated_holding["sell_date"] = sell_date
                if holding.get("sell_price"):
                    updated_holding["sell_price"] = holding["sell_price"]
            
            updated_holdings.append(updated_holding)
        
        # データベースを更新
        if updated_holdings:
            for holding in updated_holdings:
                holding_id = holding.pop("id")
                conn.execute(
                    """
                    UPDATE holdings
                    SET current_price = ?,
                        unrealized_pnl = ?,
                        return_pct = ?,
                        sell_date = COALESCE(?, sell_date),
                        sell_price = COALESCE(?, sell_price),
                        realized_pnl = ?,
                        topix_return_pct = ?,
                        excess_return_pct = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        holding.get("current_price"),
                        holding.get("unrealized_pnl"),
                        holding.get("return_pct"),
                        holding.get("sell_date"),
                        holding.get("sell_price"),
                        holding.get("realized_pnl"),
                        holding.get("topix_return_pct"),
                        holding.get("excess_return_pct"),
                        holding.get("updated_at"),
                        holding_id,
                    ),
                )
            conn.commit()
            
            # 保有銘柄全体のサマリーを更新
            update_holdings_summary(as_of_date=as_of_date)


def sell_holding(
    holding_id: int,
    sell_date: str,
    sell_price: Optional[float] = None,
) -> None:
    """
    保有銘柄を売却
    
    Args:
        holding_id: 保有銘柄のID
        sell_date: 売却日（YYYY-MM-DD）
        sell_price: 売却単価（Noneの場合は売却日の終値を使用）
    """
    with connect_db() as conn:
        # 保有銘柄を取得
        holding_df = pd.read_sql_query(
            "SELECT * FROM holdings WHERE id = ? AND sell_date IS NULL",
            conn,
            params=(holding_id,),
        )
        
        if holding_df.empty:
            raise ValueError(f"保有中の銘柄ID {holding_id} が見つかりません")
        
        holding = holding_df.iloc[0]
        code = holding["code"]
        
        # 売却単価が指定されていない場合、売却日の終値を取得
        if sell_price is None:
            price_df = pd.read_sql_query(
                """
                SELECT close
                FROM prices_daily
                WHERE code = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 1
                """,
                conn,
                params=(code, sell_date),
            )
            if price_df.empty or pd.isna(price_df["close"].iloc[0]):
                raise ValueError(f"売却日 {sell_date} の価格データが見つかりません")
            sell_price = float(price_df["close"].iloc[0])
        
        # 売却情報を更新
        conn.execute(
            """
            UPDATE holdings
            SET sell_date = ?,
                sell_price = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (sell_date, sell_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), holding_id),
        )
        conn.commit()
        
        # パフォーマンスを更新
        update_holding_performance(holding_id=holding_id, as_of_date=sell_date)
        # サマリーも更新
        update_holdings_summary(as_of_date=sell_date)


def update_holdings_summary(as_of_date: Optional[str] = None) -> None:
    """
    保有銘柄全体のパフォーマンスサマリーを計算・保存
    
    Args:
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）
    """
    with connect_db() as conn:
        # 評価日を決定
        if as_of_date is None:
            latest_date_df = pd.read_sql_query(
                "SELECT MAX(date) as max_date FROM prices_daily",
                conn
            )
            if latest_date_df.empty or pd.isna(latest_date_df["max_date"].iloc[0]):
                raise ValueError("価格データが見つかりません")
            as_of_date = latest_date_df["max_date"].iloc[0]
        
        # 保有中銘柄を取得
        active_holdings_df = pd.read_sql_query(
            "SELECT * FROM holdings WHERE sell_date IS NULL",
            conn
        )
        
        # 売却済み銘柄を取得
        sold_holdings_df = pd.read_sql_query(
            "SELECT * FROM holdings WHERE sell_date IS NOT NULL",
            conn
        )
        
        # 保有中銘柄の集計
        total_investment_active = 0.0
        total_unrealized_pnl = 0.0
        
        if not active_holdings_df.empty:
            for _, holding in active_holdings_df.iterrows():
                purchase_price = holding["purchase_price"]
                shares = holding["shares"]
                investment = purchase_price * shares
                total_investment_active += investment
                
                if pd.notna(holding.get("unrealized_pnl")):
                    total_unrealized_pnl += float(holding["unrealized_pnl"])
        
        # 売却済み銘柄の実現損益合計と投資額合計
        total_realized_pnl = 0.0
        total_investment_sold = 0.0
        
        if not sold_holdings_df.empty:
            for _, holding in sold_holdings_df.iterrows():
                purchase_price = holding["purchase_price"]
                shares = holding["shares"]
                investment = purchase_price * shares
                total_investment_sold += investment
                
                if pd.notna(holding.get("realized_pnl")):
                    total_realized_pnl += float(holding["realized_pnl"])
        
        # 総投資額
        total_investment = total_investment_active + total_investment_sold
        
        # ポートフォリオ全体のリターン（%）= (総含み損益 + 総実現損益) / 総投資額 * 100
        portfolio_return_pct = None
        if total_investment > 0:
            total_pnl = total_unrealized_pnl + total_realized_pnl
            portfolio_return_pct = (total_pnl / total_investment) * 100.0
        
        # TOPIXのパフォーマンスを計算
        # 各銘柄の保有期間に応じたTOPIXリターンを計算し、投資額で重み付き平均
        # 
        # 計算ロジック:
        # 1. 各銘柄について:
        #    - 購入日のTOPIX始値を取得
        #    - 評価日（売却済みの場合は売却日）のTOPIX終値を取得
        #    - その銘柄のTOPIXリターン = (TOPIX終値 - TOPIX始値) / TOPIX始値 * 100
        #    - 投資額 = 購入単価 * 株数
        # 2. ポートフォリオ全体のTOPIXリターン:
        #    - 各銘柄のTOPIXリターンを投資額で重み付き平均
        #    - TOPIX_return = Σ(各銘柄の投資額 * 各銘柄のTOPIXリターン) / 総投資額
        
        topix_return_pct = None
        excess_return_pct = None
        
        if total_investment > 0:
            weighted_topix_return_sum = 0.0
            
            # 保有中銘柄のTOPIXリターンを計算
            for _, holding in active_holdings_df.iterrows():
                purchase_date = holding["purchase_date"]
                purchase_price = holding["purchase_price"]
                shares = holding["shares"]
                investment = purchase_price * shares
                
                # TOPIX価格を取得（購入日の始値を使用）
                topix_buy_price = _get_topix_price(conn, purchase_date, use_open=True)
                topix_sell_price = _get_topix_price(conn, as_of_date, use_open=False)
                
                if topix_buy_price is not None and topix_sell_price is not None and topix_buy_price > 0:
                    # この銘柄の保有期間でのTOPIXリターン
                    holding_topix_return = (topix_sell_price - topix_buy_price) / topix_buy_price * 100.0
                    # 投資額で重み付け
                    weight = investment / total_investment
                    weighted_topix_return_sum += weight * holding_topix_return
            
            # 売却済み銘柄のTOPIXリターンを計算
            for _, holding in sold_holdings_df.iterrows():
                purchase_date = holding["purchase_date"]
                sell_date = holding["sell_date"]
                purchase_price = holding["purchase_price"]
                shares = holding["shares"]
                investment = purchase_price * shares
                
                # TOPIX価格を取得（購入日の始値、売却日の終値）
                topix_buy_price = _get_topix_price(conn, purchase_date, use_open=True)
                topix_sell_price = _get_topix_price(conn, sell_date, use_open=False)
                
                if topix_buy_price is not None and topix_sell_price is not None and topix_buy_price > 0:
                    # この銘柄の保有期間（購入日～売却日）でのTOPIXリターン
                    holding_topix_return = (topix_sell_price - topix_buy_price) / topix_buy_price * 100.0
                    # 投資額で重み付け
                    weight = investment / total_investment
                    weighted_topix_return_sum += weight * holding_topix_return
            
            # ポートフォリオ全体のTOPIXリターン（重み付き平均）
            topix_return_pct = weighted_topix_return_sum
            
            # 超過リターンを計算
            if portfolio_return_pct is not None:
                excess_return_pct = portfolio_return_pct - topix_return_pct
        
        # サマリーデータを作成
        summary = {
            "as_of_date": as_of_date,
            "total_investment": total_investment if total_investment > 0 else None,
            "total_unrealized_pnl": total_unrealized_pnl if total_unrealized_pnl != 0 else None,
            "total_realized_pnl": total_realized_pnl if total_realized_pnl != 0 else None,
            "portfolio_return_pct": portfolio_return_pct,
            "topix_return_pct": topix_return_pct,
            "excess_return_pct": excess_return_pct,
            "num_holdings": len(active_holdings_df),
            "num_sold": len(sold_holdings_df),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        # データベースに保存（UPSERT）
        upsert(conn, "holdings_summary", [summary], conflict_columns=["as_of_date"])


def get_holdings(
    active_only: bool = False,
    as_of_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    保有銘柄一覧を取得
    
    Args:
        active_only: Trueの場合は保有中のみ、Falseの場合はすべて
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）
        
    Returns:
        保有銘柄のリスト
    """
    with connect_db() as conn:
        if active_only:
            query = "SELECT * FROM holdings WHERE sell_date IS NULL ORDER BY purchase_date DESC, code"
        else:
            query = "SELECT * FROM holdings ORDER BY purchase_date DESC, code"
        
        holdings_df = pd.read_sql_query(query, conn)
        
        if holdings_df.empty:
            return []
        
        # パフォーマンスを更新（保有中のみ）
        if active_only:
            update_holding_performance(as_of_date=as_of_date)
            # サマリーも更新
            update_holdings_summary(as_of_date=as_of_date)
            # 再取得
            holdings_df = pd.read_sql_query(query, conn)
        else:
            # すべての銘柄を取得する場合でも、サマリーは最新の状態に更新
            update_holdings_summary(as_of_date=as_of_date)
        
        return holdings_df.to_dict("records")


def _get_topix_price(conn, date: str, use_open: bool = False) -> Optional[float]:
    """
    TOPIX価格を取得（performanceモジュールからインポートできない場合のフォールバック）
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

