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
    # /v2/fins/summary は date か code が必須。過去履歴は date で積むのが正解
    return client.get_all_pages("/fins/summary", params={"date": disclosed_date})

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
    /v2/fins/summary の1行をDBの fins_statements スキーマに変換する
    （V2 APIのカラム名 → snake_case列名、数値はfloatへ）
    
    V2 APIのカラム名:
    - DiscDate, DiscTime, Code, CurPerType, CurPerEn
    - OP, NP, Eq, EPS, BPS (実績)
    - FOP, FNP, FEPS (予想)
    - NxFOP, NxFNp, NxFEPS (次年度予想)
    - ShOutFY, TrShFY (株数)
    """
    return {
        "disclosed_date": row.get("DiscDate"),
        "disclosed_time": row.get("DiscTime"),
        "code": _normalize_code(row.get("Code")),
        "type_of_current_period": row.get("CurPerType"),
        "current_period_end": row.get("CurPerEn"),

        # 実績（FY中心）
        "operating_profit": _to_float(row.get("OP")),
        "profit": _to_float(row.get("NP")),
        "equity": _to_float(row.get("Eq")),
        "eps": _to_float(row.get("EPS")),
        "bvps": _to_float(row.get("BPS")),

        # 予想（会社予想）
        "forecast_operating_profit": _to_float(row.get("FOP")),
        "forecast_profit": _to_float(row.get("FNP")),
        "forecast_eps": _to_float(row.get("FEPS")),

        "next_year_forecast_operating_profit": _to_float(row.get("NxFOP")),
        "next_year_forecast_profit": _to_float(row.get("NxFNp")),
        "next_year_forecast_eps": _to_float(row.get("NxFEPS")),

        # 株数（時価総額計算に使えるなら使う）
        "shares_outstanding": _to_float(row.get("ShOutFY")),
        "treasury_shares": _to_float(row.get("TrShFY")),
    }


def _filter_by_disclosed_date(rows: List[Dict[str, Any]],
                             date_from: Optional[str],
                             date_to: Optional[str]) -> List[Dict[str, Any]]:
    """
    DiscDate（YYYY-MM-DD）で期間フィルタ（V2 API対応）。
    ISO形式なら文字列比較でも安全なので、pandas不要で軽量に。
    """
    if not rows:
        return rows
    if not date_from and not date_to:
        return rows

    out = []
    for r in rows:
        d = r.get("DiscDate")
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
    /v2/fins/summary は date_from/date_to を受け付けないので、
    code指定で全件取得 → DisclosedDateでローカルフィルタ。
    """
    if not code:
        raise ValueError("code is required for fetch_financial_statements")

    rows = client.get_all_pages("/fins/summary", params={"code": code})
    rows = _filter_by_disclosed_date(rows, date_from, date_to)
    return rows


def _merge_duplicate_records(mapped_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    同じ主キーを持つレコードが複数ある場合、実績値があるレコードを優先してマージする
    
    同じ主キー（disclosed_date, code, type_of_current_period, current_period_end）で
    複数のレコードがある場合、実績値（operating_profit, profit, equity等）があるレコードを優先し、
    不足している項目を他のレコードから補完する
    """
    if not mapped_rows:
        return []
    
    # 主キーでグループ化
    grouped: Dict[tuple, List[Dict[str, Any]]] = {}
    for row in mapped_rows:
        key = (
            row.get("disclosed_date"),
            row.get("code"),
            row.get("type_of_current_period"),
            row.get("current_period_end"),
        )
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(row)
    
    merged = []
    for key, rows in grouped.items():
        if len(rows) == 1:
            # 1件のみの場合はそのまま
            merged.append(rows[0])
        else:
            # 複数ある場合は、実績値があるレコードを優先
            # 実績値の有無でソート（実績値があるものを優先）
            def _has_actuals(row):
                return (
                    row.get("operating_profit") is not None or
                    row.get("profit") is not None or
                    row.get("equity") is not None or
                    row.get("eps") is not None or
                    row.get("bvps") is not None
                )
            
            rows_sorted = sorted(rows, key=_has_actuals, reverse=True)
            base_row = rows_sorted[0].copy()
            
            # 他のレコードから不足している項目を補完
            for other_row in rows_sorted[1:]:
                # 実績値の補完
                if base_row.get("operating_profit") is None and other_row.get("operating_profit") is not None:
                    base_row["operating_profit"] = other_row["operating_profit"]
                if base_row.get("profit") is None and other_row.get("profit") is not None:
                    base_row["profit"] = other_row["profit"]
                if base_row.get("equity") is None and other_row.get("equity") is not None:
                    base_row["equity"] = other_row["equity"]
                if base_row.get("eps") is None and other_row.get("eps") is not None:
                    base_row["eps"] = other_row["eps"]
                if base_row.get("bvps") is None and other_row.get("bvps") is not None:
                    base_row["bvps"] = other_row["bvps"]
                
                # 予想値の補完
                if base_row.get("forecast_operating_profit") is None and other_row.get("forecast_operating_profit") is not None:
                    base_row["forecast_operating_profit"] = other_row["forecast_operating_profit"]
                if base_row.get("forecast_profit") is None and other_row.get("forecast_profit") is not None:
                    base_row["forecast_profit"] = other_row["forecast_profit"]
                if base_row.get("forecast_eps") is None and other_row.get("forecast_eps") is not None:
                    base_row["forecast_eps"] = other_row["forecast_eps"]
                
                # その他の項目の補完
                if base_row.get("shares_outstanding") is None and other_row.get("shares_outstanding") is not None:
                    base_row["shares_outstanding"] = other_row["shares_outstanding"]
                if base_row.get("treasury_shares") is None and other_row.get("treasury_shares") is not None:
                    base_row["treasury_shares"] = other_row["treasury_shares"]
            
            merged.append(base_row)
    
    return merged


def save_financial_statements(mapped_rows: List[Dict[str, Any]]):
    """
    DBに保存（UPSERT）
    同じ主キーを持つレコードが複数ある場合、マージしてから保存
    """
    if not mapped_rows:
        return

    # 同じ主キーを持つレコードをマージ
    merged_rows = _merge_duplicate_records(mapped_rows)

    with connect_db() as conn:
        upsert(
            conn,
            "fins_statements",
            merged_rows,
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
    sleep_sec: float = 0.0,
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

        if sleep_sec > 0:
            time.sleep(sleep_sec)

    if buffer:
        save_financial_statements(buffer)