"""
取得可能な全期間のlisted_infoを取得

価格データが存在する期間（2016-01-04 ～ 2025-12-26）の各月末営業日で
listed_infoを取得します。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import List
import pandas as pd

from omanta_3rd.infra.db import connect_db
from omanta_3rd.infra.jquants import JQuantsClient
from omanta_3rd.ingest.listed import fetch_listed_info, save_listed_info
from omanta_3rd.jobs.batch_longterm_run import get_last_trading_day_of_month


def get_monthly_dates(start_date: str, end_date: str) -> List[str]:
    """
    指定期間内の各月の最終営業日を取得
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
    
    Returns:
        各月の最終営業日のリスト
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    dates = []
    current_dt = start_dt.replace(day=1)  # 月の最初の日
    
    while current_dt <= end_dt:
        year = current_dt.year
        month = current_dt.month
        
        last_trading_day = get_last_trading_day_of_month(year, month)
        if last_trading_day:
            last_trading_dt = datetime.strptime(last_trading_day, "%Y-%m-%d")
            if start_dt <= last_trading_dt <= end_dt:
                dates.append(last_trading_day)
        
        # 次の月へ
        if month == 12:
            current_dt = current_dt.replace(year=year + 1, month=1)
        else:
            current_dt = current_dt.replace(month=month + 1)
    
    return sorted(dates)


def main():
    """全期間のlisted_infoを取得"""
    print("=" * 80)
    print("全期間のlisted_info取得")
    print("=" * 80)
    
    # 価格データが存在する期間を使用
    start_date = "2016-01-04"
    end_date = "2025-12-26"
    
    print(f"期間: {start_date} ～ {end_date}")
    print()
    
    # 各月末の営業日を取得
    print("各月末の営業日を取得中...")
    monthly_dates = get_monthly_dates(start_date, end_date)
    print(f"取得対象日数: {len(monthly_dates)}日")
    print(f"最初: {monthly_dates[0] if monthly_dates else 'N/A'}")
    print(f"最後: {monthly_dates[-1] if monthly_dates else 'N/A'}")
    print()
    
    if not monthly_dates:
        print("❌ 取得対象日が見つかりませんでした")
        return
    
    # 既に取得済みの日付を確認
    print("既に取得済みの日付を確認中...")
    with connect_db() as conn:
        existing_dates_df = pd.read_sql_query(
            "SELECT DISTINCT date FROM listed_info ORDER BY date",
            conn
        )
        existing_dates = set(existing_dates_df["date"].astype(str).tolist()) if not existing_dates_df.empty else set()
        print(f"既存の日付数: {len(existing_dates)}")
    
    # 未取得の日付を抽出
    dates_to_fetch = [d for d in monthly_dates if d not in existing_dates]
    print(f"未取得の日付数: {len(dates_to_fetch)}")
    
    if not dates_to_fetch:
        print("✅ すべての日付が既に取得済みです")
        return
    
    print(f"取得対象: {dates_to_fetch[:5]}{'...' if len(dates_to_fetch) > 5 else ''}")
    print()
    
    # J-Quants APIクライアントを作成
    print("J-Quants APIクライアントを作成中...")
    client = JQuantsClient()
    print()
    
    # 各日付でlisted_infoを取得
    print("=" * 80)
    print("listed_info取得中...")
    print("=" * 80)
    
    success_count = 0
    error_count = 0
    
    for i, date in enumerate(dates_to_fetch, 1):
        print(f"[{i}/{len(dates_to_fetch)}] {date} のlisted_infoを取得中...")
        
        try:
            # データを取得
            data = fetch_listed_info(client, date)
            
            if not data:
                print(f"  ⚠️  データが空です（スキップ）")
                error_count += 1
                continue
            
            # データを保存
            save_listed_info(data)
            
            print(f"  ✅ 取得完了: {len(data)}銘柄")
            success_count += 1
            
            # APIレート制限を考慮して少し待機（必要に応じて）
            # import time
            # time.sleep(0.1)
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            error_count += 1
    
    print()
    print("=" * 80)
    print("取得結果")
    print("=" * 80)
    print(f"成功: {success_count}/{len(dates_to_fetch)}")
    print(f"エラー: {error_count}/{len(dates_to_fetch)}")
    print()
    
    # 最終的なデータ状況を確認
    print("=" * 80)
    print("最終的なデータ状況")
    print("=" * 80)
    with connect_db() as conn:
        final_dates_df = pd.read_sql_query(
            "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT date) as date_count FROM listed_info",
            conn
        )
        if not final_dates_df.empty:
            print(f"期間: {final_dates_df['min_date'].iloc[0]} ～ {final_dates_df['max_date'].iloc[0]}")
            print(f"日付数: {final_dates_df['date_count'].iloc[0]:,}日")
            
            # 各日付の銘柄数を確認
            code_count_df = pd.read_sql_query(
                """
                SELECT date, COUNT(DISTINCT code) as code_count
                FROM listed_info
                GROUP BY date
                ORDER BY date
                """,
                conn
            )
            if not code_count_df.empty:
                print(f"最初の日付の銘柄数: {code_count_df['code_count'].iloc[0]:,}銘柄")
                print(f"最後の日付の銘柄数: {code_count_df['code_count'].iloc[-1]:,}銘柄")
    
    print()
    print("=" * 80)
    print("完了")
    print("=" * 80)


if __name__ == "__main__":
    main()







