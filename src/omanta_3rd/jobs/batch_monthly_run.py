"""
各月の最終営業日でポートフォリオを作成し、パフォーマンスを計算するバッチスクリプト

使用方法:
    python -m omanta_3rd.jobs.batch_monthly_run --start 2016-01-01 --end 2025-12-28
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd

from ..infra.db import connect_db
from ..jobs.monthly_run import build_features, select_portfolio, save_features, save_portfolio
from ..backtest.performance import calculate_portfolio_performance, save_performance_to_db


def get_last_trading_day_of_month(year: int, month: int) -> Optional[str]:
    """
    指定された年月の最終営業日を取得
    
    Args:
        year: 年
        month: 月
    
    Returns:
        最終営業日（YYYY-MM-DD）、存在しない場合はNone
    """
    with connect_db() as conn:
        # その月の最後の日を取得
        if month == 12:
            last_day = datetime(year, 12, 31)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # その日以前の最新の営業日を取得
        last_trading_day_df = pd.read_sql_query(
            """
            SELECT MAX(date) AS last_date
            FROM prices_daily
            WHERE date <= ?
            """,
            conn,
            params=(last_day.strftime("%Y-%m-%d"),),
        )
        
        if last_trading_day_df.empty or pd.isna(last_trading_day_df["last_date"].iloc[0]):
            return None
        
        return str(last_trading_day_df["last_date"].iloc[0])


def get_monthly_rebalance_dates(start_date: str, end_date: str) -> List[str]:
    """
    指定期間内の各月の最終営業日を取得
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
    
    Returns:
        各月の最終営業日のリスト（YYYY-MM-DD形式）
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    rebalance_dates = []
    current_dt = start_dt.replace(day=1)  # 月の最初の日
    
    while current_dt <= end_dt:
        year = current_dt.year
        month = current_dt.month
        
        last_trading_day = get_last_trading_day_of_month(year, month)
        if last_trading_day:
            # 開始日以降、終了日以前の日付のみ追加
            last_trading_dt = datetime.strptime(last_trading_day, "%Y-%m-%d")
            if start_dt <= last_trading_dt <= end_dt:
                rebalance_dates.append(last_trading_day)
        
        # 次の月へ
        if month == 12:
            current_dt = current_dt.replace(year=year + 1, month=1)
        else:
            current_dt = current_dt.replace(month=month + 1)
    
    return sorted(rebalance_dates)


def run_monthly_portfolio_and_performance(
    rebalance_date: str,
    calculate_performance: bool = True,
    as_of_date: Optional[str] = None,
) -> dict:
    """
    指定された日付でポートフォリオを作成し、パフォーマンスを計算
    
    Args:
        rebalance_date: リバランス日（YYYY-MM-DD）
        calculate_performance: パフォーマンスを計算するか
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新）
    
    Returns:
        実行結果の辞書
    """
    result = {
        "rebalance_date": rebalance_date,
        "portfolio_created": False,
        "performance_calculated": False,
        "error": None,
    }
    
    try:
        with connect_db() as conn:
            # 1. 特徴量を構築
            print(f"[{rebalance_date}] 特徴量を構築中...")
            feat = build_features(conn, rebalance_date)
            
            if feat.empty:
                result["error"] = "特徴量が空です"
                return result
            
            # 2. ポートフォリオを選択
            print(f"[{rebalance_date}] ポートフォリオを選択中...")
            portfolio = select_portfolio(feat)
            
            if portfolio.empty:
                result["error"] = "ポートフォリオが空です"
                return result
            
            # 3. データベースに保存
            print(f"[{rebalance_date}] データベースに保存中...")
            save_features(conn, feat)
            save_portfolio(conn, portfolio)
            
            result["portfolio_created"] = True
            result["num_stocks"] = len(portfolio)
            
            # 4. パフォーマンスを計算
            if calculate_performance:
                print(f"[{rebalance_date}] パフォーマンスを計算中...")
                performance = calculate_portfolio_performance(rebalance_date, as_of_date)
                
                if "error" not in performance:
                    save_performance_to_db(performance)
                    result["performance_calculated"] = True
                    result["total_return_pct"] = performance.get("total_return_pct")
                else:
                    result["error"] = performance.get("error", "パフォーマンス計算エラー")
            
            print(f"[{rebalance_date}] ✅ 完了")
            return result
            
    except Exception as e:
        result["error"] = str(e)
        import traceback
        traceback.print_exc()
        return result


def main(
    start_date: str,
    end_date: str,
    calculate_performance: bool = True,
    as_of_date: Optional[str] = None,
    skip_existing: bool = True,
):
    """
    メイン処理
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        calculate_performance: パフォーマンスを計算するか
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新）
        skip_existing: 既存のポートフォリオをスキップするか
    """
    print("=" * 80)
    print("バッチ月次ポートフォリオ作成・パフォーマンス計算")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"パフォーマンス計算: {'有効' if calculate_performance else '無効'}")
    if as_of_date:
        print(f"評価日: {as_of_date}")
    else:
        print(f"評価日: 最新の価格データ")
    print("=" * 80)
    print()
    
    # 各月の最終営業日を取得
    print("各月の最終営業日を取得中...")
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"✅ {len(rebalance_dates)}個のリバランス日を取得しました")
    print(f"   最初: {rebalance_dates[0] if rebalance_dates else 'N/A'}")
    print(f"   最後: {rebalance_dates[-1] if rebalance_dates else 'N/A'}")
    print()
    
    if not rebalance_dates:
        print("❌ リバランス日が見つかりませんでした")
        return 1
    
    # 既存のポートフォリオを確認
    if skip_existing:
        with connect_db() as conn:
            existing_dates_df = pd.read_sql_query(
                "SELECT DISTINCT rebalance_date FROM portfolio_monthly",
                conn
            )
            existing_dates = set(existing_dates_df["rebalance_date"].tolist()) if not existing_dates_df.empty else set()
            rebalance_dates = [d for d in rebalance_dates if d not in existing_dates]
            print(f"既存のポートフォリオをスキップ: {len(rebalance_dates)}個の日付を処理します")
            print()
    
    # 各日付でポートフォリオを作成
    results = []
    success_count = 0
    error_count = 0
    
    for i, rebalance_date in enumerate(rebalance_dates, 1):
        print(f"[{i}/{len(rebalance_dates)}] {rebalance_date} を処理中...")
        result = run_monthly_portfolio_and_performance(
            rebalance_date,
            calculate_performance=calculate_performance,
            as_of_date=as_of_date,
        )
        results.append(result)
        
        if result["error"]:
            error_count += 1
            print(f"  ❌ エラー: {result['error']}")
        else:
            success_count += 1
            if result["portfolio_created"]:
                print(f"  ✅ ポートフォリオ作成成功 ({result.get('num_stocks', 0)}銘柄)")
            if result["performance_calculated"]:
                return_pct = result.get("total_return_pct")
                if return_pct is not None:
                    print(f"  ✅ パフォーマンス計算成功 (リターン: {return_pct:.2f}%)")
        print()
    
    # 結果サマリー
    print("=" * 80)
    print("【実行結果サマリー】")
    print("=" * 80)
    print(f"総処理数: {len(rebalance_dates)}")
    print(f"成功: {success_count}")
    print(f"エラー: {error_count}")
    print()
    
    if error_count > 0:
        print("エラーが発生した日付:")
        for result in results:
            if result["error"]:
                print(f"  - {result['rebalance_date']}: {result['error']}")
        print()
    
    print("=" * 80)
    
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="各月の最終営業日でポートフォリオを作成し、パフォーマンスを計算",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 2016-01-01から2025-12-28までの各月の最終営業日でポートフォリオを作成
  python -m omanta_3rd.jobs.batch_monthly_run --start 2016-01-01 --end 2025-12-28
  
  # パフォーマンス計算をスキップ
  python -m omanta_3rd.jobs.batch_monthly_run --start 2016-01-01 --end 2025-12-28 --no-performance
  
  # 特定の評価日でパフォーマンスを計算
  python -m omanta_3rd.jobs.batch_monthly_run --start 2016-01-01 --end 2025-12-28 --as-of-date 2025-12-28
  
  # 既存のポートフォリオも再作成
  python -m omanta_3rd.jobs.batch_monthly_run --start 2016-01-01 --end 2025-12-28 --no-skip-existing
        """
    )
    
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="開始日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="終了日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--as-of-date",
        type=str,
        dest="as_of_date",
        default=None,
        help="評価日（YYYY-MM-DD、Noneの場合は最新）",
    )
    parser.add_argument(
        "--no-performance",
        action="store_true",
        help="パフォーマンス計算をスキップ",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="既存のポートフォリオも再作成",
    )
    
    args = parser.parse_args()
    
    sys.exit(main(
        start_date=args.start,
        end_date=args.end,
        calculate_performance=not args.no_performance,
        as_of_date=args.as_of_date,
        skip_existing=not args.no_skip_existing,
    ))







