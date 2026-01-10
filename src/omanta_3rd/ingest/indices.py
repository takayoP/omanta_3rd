"""指数データ（TOPIXなど）を保存"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from ..infra.db import connect_db, upsert
from ..infra.jquants import JQuantsClient


# TOPIX指数のコード定数
TOPIX_CODE = "0000"


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


def fetch_index_by_date(client: JQuantsClient, index_code: str, date: str) -> List[Dict[str, Any]]:
    """
    指数データを取得
    
    TOPIX指数の場合は専用エンドポイント(/v2/indices/bars/daily/topix)を使用します。
    その他の指数の場合は従来のエンドポイント(/v2/indices/bars/daily)を使用します。
    
    Args:
        client: J-Quants APIクライアント
        index_code: 指数コード（例: "0000" はTOPIX指数）
        date: 日付（YYYY-MM-DD）
        
    Returns:
        指数データのリスト
    """
    if index_code == TOPIX_CODE:
        # TOPIX専用エンドポイント
        rows = client.get_all_pages("/indices/bars/daily/topix", params={"date": date})
    else:
        # その他の指数用エンドポイント
        rows = client.get_all_pages("/indices/bars/daily", params={"code": index_code, "date": date})
    return rows


def fetch_index_by_range(
    client: JQuantsClient, 
    index_code: str, 
    date_from: str, 
    date_to: str
) -> List[Dict[str, Any]]:
    """
    指数データを期間指定で取得
    
    TOPIX指数の場合は専用エンドポイント(/v2/indices/bars/daily/topix)を使用します。
    その他の指数の場合は従来のエンドポイント(/v2/indices/bars/daily)を使用します。
    
    Args:
        client: J-Quants APIクライアント
        index_code: 指数コード（例: "0000" はTOPIX指数）
        date_from: 開始日（YYYY-MM-DD）
        date_to: 終了日（YYYY-MM-DD）
        
    Returns:
        指数データのリスト
    """
    if index_code == TOPIX_CODE:
        # TOPIX専用エンドポイント
        rows = client.get_all_pages(
            "/indices/bars/daily/topix", 
            params={"from": date_from, "to": date_to}
        )
    else:
        # その他の指数用エンドポイント
        rows = client.get_all_pages(
            "/indices/bars/daily", 
            params={"code": index_code, "from": date_from, "to": date_to}
        )
    return rows


def _map_index_row(row: Dict[str, Any], index_code: str) -> Dict[str, Any]:
    """
    APIの1行をDBスキーマに合わせて変換
    
    V2 APIのカラム名:
    - Date, Code, O (始値), H (高値), L (安値), C (終値)
    """
    return {
        "date": row.get("Date"),
        "index_code": index_code,
        "open": row.get("O"),
        "high": row.get("H"),
        "low": row.get("L"),
        "close": row.get("C"),
    }


def save_index_data(data: List[Dict[str, Any]]):
    """
    指数データをDBに保存（UPSERT）
    """
    if not data:
        return
    with connect_db() as conn:
        upsert(conn, "index_daily", data, conflict_columns=["date", "index_code"])


def ingest_index_data(
    index_code: str,
    start_date: str,
    end_date: str,
    client: Optional[JQuantsClient] = None,
    sleep_sec: float = 0.0,
    batch_size: int = 1000,
):
    """
    指数データを取り込み（start_date〜end_date）
    
    Args:
        index_code: 指数コード（例: "0000" はTOPIX指数）
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        client: J-Quants APIクライアント
        sleep_sec: 追加の待機時間（デフォルト: 0.0。JQuantsClientでレート制限管理済みのため通常は不要）
        batch_size: 一括保存する件数
    """
    if client is None:
        client = JQuantsClient()
    
    # 期間指定で一括取得を試みる（効率的）
    try:
        print(f"[indices] Fetching {index_code} data from {start_date} to {end_date} (bulk)")
        rows = fetch_index_by_range(client, index_code, start_date, end_date)
        if rows:
            mapped = [_map_index_row(r, index_code) for r in rows]
            save_index_data(mapped)
            print(f"[indices] Saved {len(mapped)} records for {index_code}")
        return
    except Exception as e:
        # 一括取得が失敗した場合は日付ごとに取得
        print(f"[indices] Bulk fetch failed, falling back to daily fetch: {e}")
    
    # 日付ごとに取得（フォールバック）
    dates = _daterange(start_date, end_date)
    buf: List[Dict[str, Any]] = []
    
    for i, d in enumerate(dates, start=1):
        print(f"[indices] date {i}/{len(dates)}: {d}")
        
        try:
            rows = fetch_index_by_date(client, index_code, d)
            if rows:
                mapped = [_map_index_row(r, index_code) for r in rows]
                buf.extend(mapped)
        except Exception as e:
            print(f"[indices] Error fetching {index_code} for {d}: {e}")
            continue
        
        if len(buf) >= batch_size:
            save_index_data(buf)
            buf.clear()
        
        if sleep_sec > 0:
            time.sleep(sleep_sec)
    
    if buf:
        save_index_data(buf)

