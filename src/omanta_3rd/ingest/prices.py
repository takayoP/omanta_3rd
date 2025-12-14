"""prices_daily を保存"""

from typing import List, Dict, Any, Optional

from ..infra.db import connect_db, upsert
from ..infra.jquants import JQuantsClient


def fetch_prices(
    client: JQuantsClient,
    code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    価格データを取得
    
    Args:
        client: J-Quants APIクライアント
        code: 銘柄コード（Noneで全銘柄）
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        
    Returns:
        価格データのリスト
    """
    # J-Quants APIの/prices/daily_quotesエンドポイントは
    # dateパラメータ（単一の日付）またはcodeパラメータが必要
    # 日付範囲を指定する場合は、各日付ごとにリクエストする必要がある可能性
    
    all_data = []
    
    if start_date and end_date:
        # 日付範囲を指定する場合、各日付ごとにリクエスト
        from datetime import datetime, timedelta
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        current = start
        
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            params = {"date": date_str}
            if code:
                params["code"] = code
            
            try:
                data = client.get_all_pages("/prices/daily_quotes", params=params)
                all_data.extend(data)
            except Exception as e:
                print(f"警告: {date_str}のデータ取得に失敗: {e}")
            
            current += timedelta(days=1)
    else:
        # 単一の日付またはcodeのみ
        params = {}
        if code:
            params["code"] = code
        # dateパラメータが必要な場合は、end_dateまたはstart_dateを使用
        if end_date:
            params["date"] = end_date
        elif start_date:
            params["date"] = start_date
        
        data = client.get_all_pages("/prices/daily_quotes", params=params)
        all_data.extend(data)
    
    # データ形式をDBスキーマに合わせて変換
    result = []
    for item in all_data:
        result.append({
            "date": item.get("Date", ""),
            "code": item.get("Code", ""),
            "adj_close": _to_float(item.get("AdjustmentClose")),
            "adj_volume": _to_float(item.get("AdjustmentVolume")),
            "turnover_value": _to_float(item.get("TurnoverValue")),
        })
    
    return result


def _to_float(value: Any) -> Optional[float]:
    """値をfloatに変換（None/空文字はNoneを返す）"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def save_prices(data: List[Dict[str, Any]]):
    """
    価格データをDBに保存
    
    Args:
        data: 価格データのリスト
    """
    with connect_db() as conn:
        upsert(conn, "prices_daily", data, conflict_columns=["date", "code"])


def ingest_prices(
    start_date: str,
    end_date: str,
    code: Optional[str] = None,
    client: Optional[JQuantsClient] = None,
):
    """
    価格データを取り込み
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        code: 銘柄コード（Noneで全銘柄）
        client: J-Quants APIクライアント（Noneの場合は新規作成）
    """
    if client is None:
        client = JQuantsClient()
    
    data = fetch_prices(client, code=code, start_date=start_date, end_date=end_date)
    save_prices(data)

