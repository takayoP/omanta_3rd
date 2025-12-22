"""prices_daily を保存"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from ..infra.db import connect_db, upsert
from ..infra.jquants import JQuantsClient


def _normalize_code(code: Any) -> str:
    """
    - 通常株：4桁
    - 5桁で末尾0（例: 72030）は 7203 に正規化
    - 末尾0でない5桁（ETF/ETN等の可能性）は取り込まない（空文字を返す）
    """
    if code is None:
        return ""
    s = str(code).strip()
    if len(s) == 5 and s.endswith("0"):
        return s[:4]
    if len(s) == 5:
        return ""  # ←ここで除外
    return s


def _daterange(date_from: str, date_to: str) -> List[str]:
    """
    date_from〜date_to（YYYY-MM-DD）の全日付を返す（週末含む）
    """
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    out = []
    d = start
    while d <= end:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def fetch_prices_by_date(client: JQuantsClient, date: str) -> List[Dict[str, Any]]:
    """
    /prices/daily_quotes は date か code が必須。
    ここでは date 指定で1日分を取得する。
    """
    rows = client.get_all_pages("/prices/daily_quotes", params={"date": date})
    return rows


def _map_price_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    APIの1行をDBスキーマに合わせて変換
    
    J-Quants APIの/prices/daily_quotesエンドポイントから取得できるフィールド:
    - Close: 終値（調整前）
    - AdjustmentClose: 調整済終値
    - AdjustmentFactor: 調整係数
    - AdjustmentVolume: 調整済出来高
    - TurnoverValue: 売買代金
    """
    code = _normalize_code(row.get("Code"))
    
    # Closeフィールドを取得（調整前終値）
    close = row.get("Close")
    # CloseがNoneの場合は、AdjustmentCloseを使用（フォールバック）
    # ただし、通常はCloseが提供されるはず
    # 注意: CloseとAdjustmentCloseの両方がNoneの場合は、その日が休場日や取引がなかった可能性がある
    if close is None:
        close = row.get("AdjustmentClose")
    
    return {
        "date": row.get("Date"),
        "code": code,
        "close": close,  # 調整前終値（Closeフィールドから取得）
        "adj_close": row.get("AdjustmentClose"),  # 調整済終値
        "adj_volume": row.get("AdjustmentVolume"),  # 調整済出来高
        "turnover_value": row.get("TurnoverValue"),  # 売買代金
        "adjustment_factor": row.get("AdjustmentFactor"),  # 調整係数
    }


def save_prices(data: List[Dict[str, Any]]):
    """
    価格データをDBに保存（UPSERT）
    """
    if not data:
        return
    with connect_db() as conn:
        upsert(conn, "prices_daily", data, conflict_columns=["date", "code"])


def ingest_prices(
    start_date: str,
    end_date: str,
    client: Optional[JQuantsClient] = None,
    sleep_sec: float = 0.2,
    batch_size: int = 5000,
):
    """
    価格データを取り込み（start_date〜end_date）

    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        client: J-Quants APIクライアント
        sleep_sec: レート制限対策の待機
        batch_size: 一括保存する件数
    """
    if client is None:
        client = JQuantsClient()

    dates = _daterange(start_date, end_date)

    buf: List[Dict[str, Any]] = []
    for i, d in enumerate(dates, start=1):
        print(f"[prices] date {i}/{len(dates)}: {d}")

        rows = fetch_prices_by_date(client, d)
        if rows:
            mapped = [_map_price_row(r) for r in rows]
            # code が空の行（末尾0でない5桁など）を除外
            mapped = [m for m in mapped if m.get("code")]
            buf.extend(mapped)

        if len(buf) >= batch_size:
            save_prices(buf)
            buf.clear()

        time.sleep(sleep_sec)

    if buf:
        save_prices(buf)
