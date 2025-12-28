"""決算発表予定日の管理"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd

from ..infra.db import connect_db, upsert


def add_earnings_announcement(
    code: str,
    announcement_date: str,
    period_type: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """
    決算発表予定日を追加
    
    Args:
        code: 銘柄コード
        announcement_date: 決算発表予定日（YYYY-MM-DD）
        period_type: 期間種別（FY / 1Q / 2Q / 3Q）
        period_end: 当期末日（YYYY-MM-DD）
        
    Returns:
        追加された決算発表予定日の情報
    """
    with connect_db() as conn:
        earnings = {
            "code": code,
            "announcement_date": announcement_date,
            "period_type": period_type,
            "period_end": period_end,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        upsert(
            conn,
            "earnings_calendar",
            [earnings],
            conflict_columns=["code", "announcement_date", "period_type", "period_end"],
        )
        return earnings


def get_earnings_announcements(
    code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    決算発表予定日を取得
    
    Args:
        code: 銘柄コード（Noneの場合はすべて）
        date_from: 開始日（YYYY-MM-DD）
        date_to: 終了日（YYYY-MM-DD）
        
    Returns:
        決算発表予定日のリスト
    """
    with connect_db() as conn:
        query = "SELECT * FROM earnings_calendar WHERE 1=1"
        params = []
        
        if code:
            query += " AND code = ?"
            params.append(code)
        
        if date_from:
            query += " AND announcement_date >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND announcement_date <= ?"
            params.append(date_to)
        
        query += " ORDER BY announcement_date, code"
        
        df = pd.read_sql_query(query, conn, params=params if params else None)
        return df.to_dict("records")


def get_next_trading_day(date_str: str) -> Optional[str]:
    """
    指定日の翌営業日を取得
    
    Args:
        date_str: 基準日（YYYY-MM-DD）
        
    Returns:
        翌営業日（YYYY-MM-DD）、存在しない場合はNone
    """
    from datetime import datetime, timedelta
    
    with connect_db() as conn:
        # 価格データが存在する最初の日付を取得
        next_date_df = pd.read_sql_query(
            """
            SELECT MIN(date) AS next_date
            FROM prices_daily
            WHERE date > ?
            """,
            conn,
            params=(date_str,),
        )
        
        if next_date_df.empty or pd.isna(next_date_df["next_date"].iloc[0]):
            return None
        
        return next_date_df["next_date"].iloc[0]


def check_upcoming_announcements(as_of_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    保有銘柄の翌営業日の決算発表予定日をチェック
    
    Args:
        as_of_date: 基準日（YYYY-MM-DD、Noneの場合は今日）
        
    Returns:
        翌営業日に決算発表予定がある保有銘柄のリスト
    """
    from datetime import datetime
    
    if as_of_date is None:
        as_of_date = datetime.now().strftime("%Y-%m-%d")
    
    next_trading_day = get_next_trading_day(as_of_date)
    if not next_trading_day:
        return []
    
    with connect_db() as conn:
        # 保有中の銘柄を取得
        holdings_df = pd.read_sql_query(
            """
            SELECT DISTINCT code, company_name
            FROM holdings
            WHERE sell_date IS NULL
            """,
            conn,
        )
        
        if holdings_df.empty:
            return []
        
        codes = holdings_df["code"].tolist()
        placeholders = ",".join(["?"] * len(codes))
        
        # 翌営業日に決算発表予定がある銘柄を取得
        earnings_df = pd.read_sql_query(
            f"""
            SELECT ec.*, h.company_name
            FROM earnings_calendar ec
            INNER JOIN holdings h ON ec.code = h.code AND h.sell_date IS NULL
            WHERE ec.announcement_date = ?
              AND ec.code IN ({placeholders})
            """,
            conn,
            params=[next_trading_day] + codes,
        )
        
        if earnings_df.empty:
            return []
        
        return earnings_df.to_dict("records")

