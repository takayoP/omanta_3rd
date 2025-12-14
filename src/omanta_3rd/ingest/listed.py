"""listed_info を保存"""

from typing import List, Dict, Any, Optional

from ..infra.db import connect_db, upsert
from ..infra.jquants import JQuantsClient


def fetch_listed_info(client: JQuantsClient, date: str) -> List[Dict[str, Any]]:
    """
    銘柄情報を取得
    
    Args:
        client: J-Quants APIクライアント
        date: 取得日（YYYY-MM-DD）
        
    Returns:
        銘柄情報のリスト
    """
    # エンドポイントは実際のJ-Quants APIに合わせて調整
    data = client.get_all_pages("/listed/info", params={"date": date})
    
    # データ形式をDBスキーマに合わせて変換
    result = []
    for item in data:
        result.append({
            "date": date,
            "code": item.get("Code", ""),
            "company_name": item.get("CompanyName", ""),
            "market_name": item.get("MarketName", ""),
            "sector17": item.get("Sector17Code", ""),
            "sector33": item.get("Sector33Code", ""),
        })
    
    return result


def save_listed_info(data: List[Dict[str, Any]]):
    """
    銘柄情報をDBに保存
    
    Args:
        data: 銘柄情報のリスト
    """
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

