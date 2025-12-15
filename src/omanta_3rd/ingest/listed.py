"""listed_info を保存"""

from __future__ import annotations

from typing import List, Dict, Any, Optional

from ..infra.db import connect_db, upsert
from ..infra.jquants import JQuantsClient


def _normalize_code(code: Any) -> str:
    """
    J-QuantsのCodeは5桁（例: '72030'）の場合があるので、
    DBは4桁に統一（末尾0なら落とす）。
    """
    if code is None:
        return ""
    s = str(code).strip()
    if len(s) == 5 and s.endswith("0"):
        return s[:4]
    return s


def fetch_listed_info(client: JQuantsClient, date: str) -> List[Dict[str, Any]]:
    """
    銘柄情報を取得してDBスキーマに合わせて変換

    Args:
        client: J-Quants APIクライアント
        date: 取得日（YYYY-MM-DD）

    Returns:
        DBに保存する形式の銘柄情報リスト
    """
    # J-Quants /listed/info のレスポンスは {"info":[...]} だが
    # client.get_all_pages は配列キーを自動検出して list を返す実装
    rows = client.get_all_pages("/listed/info", params={"date": date})

    result: List[Dict[str, Any]] = []
    for item in rows:
        result.append(
            {
                "date": item.get("Date") or date,
                "code": _normalize_code(item.get("Code")),
                "company_name": item.get("CompanyName") or "",
                # 正しいキーは MarketCodeName
                "market_name": item.get("MarketCodeName") or "",
                # DBは名称で持つ（同業比較に使いやすい）
                "sector17": item.get("Sector17CodeName") or "",
                "sector33": item.get("Sector33CodeName") or "",
            }
        )

    return result


def save_listed_info(data: List[Dict[str, Any]]):
    """
    銘柄情報をDBに保存

    Args:
        data: 銘柄情報のリスト
    """
    if not data:
        return
    with connect_db() as conn:
        upsert(conn, "listed_info", data, conflict_columns=["date", "code"])


def ingest_listed_info(date: str, client: Optional[JQuantsClient] = None):
    """
    銘柄情報を取り込み

    Args:
        date: 取得日（YYYY-MM-DD）
        client: J-Quants APIクライアント（Noneの場合は新規作成）
    """
    if client is None:
        client = JQuantsClient()

    data = fetch_listed_info(client, date)
    save_listed_info(data)
