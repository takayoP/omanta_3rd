"""
既存のprices_dailyテーブルのcloseカラムを更新
APIからCloseを再取得して更新する
"""

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.infra.jquants import JQuantsClient
from src.omanta_3rd.ingest.prices import _map_price_row, save_prices
import pandas as pd
import time

def update_close_for_date_range(start_date: str, end_date: str, code: str = None):
    """
    指定期間のcloseカラムを更新
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        code: 銘柄コード（Noneで全銘柄）
    """
    client = JQuantsClient()
    
    # 日付範囲を生成
    from datetime import datetime, timedelta
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    dates = []
    d = start
    while d <= end:
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    
    print(f"更新対象: {len(dates)}日分")
    if code:
        print(f"銘柄コード: {code}")
    
    buf = []
    for i, date_str in enumerate(dates, start=1):
        print(f"[{i}/{len(dates)}] {date_str} を処理中...")
        
        try:
            # APIからデータを取得
            params = {"date": date_str}
            if code:
                params["code"] = code
            
            rows = client.get_all_pages("/prices/daily_quotes", params=params)
            
            if rows:
                # マッピング
                mapped = [_map_price_row(r) for r in rows]
                # codeが空の行を除外
                mapped = [m for m in mapped if m.get("code")]
                
                # closeがNoneのレコードを確認（データ欠損の可能性）
                # CloseとAdjustmentCloseの両方がNoneの場合は、API側でデータが欠損している
                null_close_count = sum(1 for m in mapped if m.get("close") is None)
                if null_close_count > 0:
                    # 詳細を確認（サンプル）
                    null_samples = [m for m in mapped if m.get("close") is None][:3]
                    if null_samples:
                        sample_codes = [m.get("code") for m in null_samples if m.get("code")]
                        codes_str = ", ".join(sample_codes) if sample_codes else "N/A"
                        print(f"  情報: {null_close_count}件のレコードでcloseがNone（データ欠損の可能性、例: {codes_str}）")
                
                buf.extend(mapped)
            
            # バッチサイズに達したら保存
            if len(buf) >= 1000:
                save_prices(buf)
                print(f"  {len(buf)}件を保存しました")
                buf.clear()
            
            time.sleep(0.2)  # レート制限対策
            
        except Exception as e:
            print(f"  エラー: {e}")
            continue
    
    # 残りを保存
    if buf:
        save_prices(buf)
        print(f"  残り{len(buf)}件を保存しました")
    
    print("更新が完了しました")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("使用方法: python _update_close_column.py <start_date> <end_date> [code]")
        print("例: python _update_close_column.py 2025-12-01 2025-12-19 7419")
        sys.exit(1)
    
    start_date = sys.argv[1]
    end_date = sys.argv[2]
    code = sys.argv[3] if len(sys.argv) > 3 else None
    
    update_close_for_date_range(start_date, end_date, code)
