"""listed_info を保存"""

from __future__ import annotations

from typing import List, Dict, Any, Optional

from ..infra.db import connect_db, upsert
from ..infra.jquants import JQuantsClient


def _normalize_code(code: Any) -> str:
    """
    J-QuantsのCodeは5桁（例: '72030'）の場合があるため、
    DBでは4桁に統一する。
    - 5桁なら先頭4桁に落とす（安全側）
    """
    if code is None:
        return ""
    s = str(code).strip()
    if len(s) == 5:
        return s[:4]
    return s


def fetch_listed_info(client: JQuantsClient, date: str) -> List[Dict[str, Any]]:
    """
    /v2/equities/master から銘柄情報を取得し、DBスキーマに合わせて変換して返す
    
    V2 APIのカラム名:
    - Date, Code, CoName, MktNm, S17Nm, S33Nm
    """
    rows = client.get_all_pages("/equities/master", params={"date": date})

    result: List[Dict[str, Any]] = []
    for item in rows:
        result.append(
            {
                # API側にもDateがあるが、引数dateを優先してもOK
                "date": item.get("Date") or date,
                "code": _normalize_code(item.get("Code")),
                "company_name": item.get("CoName") or "",
                "market_name": item.get("MktNm") or "",
                "sector17": item.get("S17Nm") or "",
                "sector33": item.get("S33Nm") or "",
            }
        )

    return result


def save_listed_info(data: List[Dict[str, Any]]):
    """銘柄情報をDBに保存（UPSERT）"""
    if not data:
        return
    with connect_db() as conn:
        upsert(conn, "listed_info", data, conflict_columns=["date", "code"])


def ingest_listed_info(date: str, client: Optional[JQuantsClient] = None):
    """銘柄情報を取り込み"""
    if client is None:
        client = JQuantsClient()

    data = fetch_listed_info(client, date)
    save_listed_info(data)
