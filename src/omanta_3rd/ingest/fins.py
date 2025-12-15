"""fins_statements を保存"""

from __future__ import annotations

import time
from typing import List, Dict, Any, Optional, Iterable

from ..infra.db import connect_db, upsert
from ..infra.jquants import JQuantsClient

from datetime import date, datetime, timedelta


# ---------- helpers ----------

def _daterange(d1: str, d2: str):
    start = datetime.strptime(d1, "%Y-%m-%d").date()
    end = datetime.strptime(d2, "%Y-%m-%d").date()
    d = start
    while d <= end:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)

def fetch_financial_statements_by_date(client: JQuantsClient, disclosed_date: str):
    # /fins/statements は date か code が必須。過去履歴は date で積むのが正解
    return client.get_all_pages("/fins/statements", params={"date": disclosed_date})

def _to_float(value: Any) -> Optional[float]:
    """値をfloatに変換（None/空文字はNone）"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _normalize_code(local_code: str) -> str:
    """
    J-QuantsのLocalCode(5桁, 例: '72030') をDB用4桁に正規化。
    基本は末尾0を落とす想定。
    """
    if not local_code:
        return local_code
    s = str(local_code)
    if len(s) == 5 and s.endswith("0"):
        return s[:4]
    # 想定外でも落とさない（安全側）
    return s


def _map_row_to_db(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    /fins/statements の1行をDBの fins_statements スキーマに変換する
    （APIキー → snake_case列名、数値はfloatへ）
    """
    return {
        "disclosed_date": row.get("DisclosedDate"),
        "disclosed_time": row.get("DisclosedTime"),
        "code": _normalize_code(row.get("LocalCode")),
        "type_of_current_period": row.get("TypeOfCurrentPeriod"),
        "current_period_end": row.get("CurrentPeriodEndDate"),

        # 実績（FY中心）
        "operating_profit": _to_float(row.get("OperatingProfit")),
        "profit": _to_float(row.get("Profit")),
        "equity": _to_float(row.get("Equity")),
        "eps": _to_float(row.get("EarningsPerShare")),
        "bvps": _to_float(row.get("BookValuePerShare")),

        # 予想（会社予想）
        "forecast_operating_profit": _to_float(row.get("ForecastOperatingProfit")),
        "forecast_profit": _to_float(row.get("ForecastProfit")),
        "forecast_eps": _to_float(row.get("ForecastEarningsPerShare")),

        "next_year_forecast_operating_profit": _to_float(row.get("NextYearForecastOperatingProfit")),
        "next_year_forecast_profit": _to_float(row.get("NextYearForecastProfit")),
        "next_year_forecast_eps": _to_float(row.get("NextYearForecastEarningsPerShare")),

        # 株数（時価総額計算に使えるなら使う）
        "shares_outstanding": _to_float(
            row.get("NumberOfIssuedAndOutstandingSharesAtTheEndOfFiscalYearIncludingTreasuryStock")
        ),
        "treasury_shares": _to_float(row.get("NumberOfTreasuryStockAtTheEndOfFiscalYear")),
    }


def _filter_by_disclosed_date(rows: List[Dict[str, Any]],
                             date_from: Optional[str],
                             date_to: Optional[str]) -> List[Dict[str, Any]]:
    """
    DisclosedDate（YYYY-MM-DD）で期間フィルタ。
    ISO形式なら文字列比較でも安全なので、pandas不要で軽量に。
    """
    if not rows:
        return rows
    if not date_from and not date_to:
        return rows

    out = []
    for r in rows:
        d = r.get("DisclosedDate")
        if not d:
            continue
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        out.append(r)
    return out


def _get_all_codes_from_db() -> List[str]:
    """
    code指定がないときに、DBのlisted_info最新日から銘柄コード一覧を取得。
    """
    with connect_db(read_only=True) as conn:
        max_date = conn.execute("SELECT MAX(date) FROM listed_info").fetchone()[0]
        if not max_date:
            raise RuntimeError("listed_info が空です。先に --target listed を実行してください。")
        rows = conn.execute(
            "SELECT code FROM listed_info WHERE date = ? ORDER BY code",
            (max_date,),
        ).fetchall()
        return [r["code"] for r in rows]


# ---------- API fetch ----------

def fetch_financial_statements(
    client: JQuantsClient,
    code: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    /fins/statements は date_from/date_to を受け付けないので、
    code指定で全件取得 → DisclosedDateでローカルフィルタ。
    """
    if not code:
        raise ValueError("code is required for fetch_financial_statements")

    rows = client.get_all_pages("/fins/statements", params={"code": code})
    rows = _filter_by_disclosed_date(rows, date_from, date_to)
    return rows


def save_financial_statements(mapped_rows: List[Dict[str, Any]]):
    """
    DBに保存（UPSERT）
    """
    if not mapped_rows:
        return

    with connect_db() as conn:
        upsert(
            conn,
            "fins_statements",
            mapped_rows,
            conflict_columns=[
                "disclosed_date",
                "code",
                "type_of_current_period",
                "current_period_end",
            ],
        )


def ingest_financial_statements(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    code: Optional[str] = None,
    client: Optional[JQuantsClient] = None,
    sleep_sec: float = 0.2,
    batch_size: int = 2000,
):
    if client is None:
        client = JQuantsClient()

    buffer: List[Dict[str, Any]] = []

    if code:
        # スポット用途：codeで取得（必要なら残す）
        rows = fetch_financial_statements(client, code=code, date_from=date_from, date_to=date_to)
        buffer.extend([_map_row_to_db(r) for r in rows])
        save_financial_statements(buffer)
        return

    # 通常：dateで履歴を積み上げる
    if not date_from or not date_to:
        raise ValueError("date_from と date_to は必須です（code指定がない場合）")

    total_days = 0
    for d in _daterange(date_from, date_to):
        total_days += 1

        # 進捗（文字化けしにくい英数字）
        print(f"[fins] date: {d}")

        rows = fetch_financial_statements_by_date(client, disclosed_date=d)
        if rows:
            buffer.extend([_map_row_to_db(r) for r in rows])

        if len(buffer) >= batch_size:
            save_financial_statements(buffer)
            buffer.clear()

        time.sleep(sleep_sec)

    if buffer:
        save_financial_statements(buffer)