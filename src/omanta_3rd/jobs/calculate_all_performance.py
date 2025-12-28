"""
既存のポートフォリオに対してパフォーマンス計算のみを実行するスクリプト

使用方法:
    python -m omanta_3rd.jobs.calculate_all_performance
    python -m omanta_3rd.jobs.calculate_all_performance --as-of-date 2025-12-28
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional
import pandas as pd

from ..infra.db import connect_db
from ..backtest.performance import (
    calculate_portfolio_performance,
    calculate_all_portfolios_performance,
    save_performance_to_db,
)


def main(
    as_of_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    メイン処理
    
    Args:
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）
        start_date: 開始日（YYYY-MM-DD、この日以降のポートフォリオのみ計算）
        end_date: 終了日（YYYY-MM-DD、この日以前のポートフォリオのみ計算）
    """
    print("=" * 80)
    print("既存ポートフォリオのパフォーマンス計算")
    print("=" * 80)
    if as_of_date:
        print(f"評価日: {as_of_date}")
    else:
        print(f"評価日: 最新の価格データ")
    if start_date:
        print(f"開始日: {start_date}")
    if end_date:
        print(f"終了日: {end_date}")
    print("=" * 80)
    print()
    
    # 既存のポートフォリオを取得
    with connect_db() as conn:
        query = "SELECT DISTINCT rebalance_date FROM portfolio_monthly"
        params = []
        
        if start_date or end_date:
            conditions = []
            if start_date:
                conditions.append("rebalance_date >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("rebalance_date <= ?")
                params.append(end_date)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY rebalance_date"
        
        rebalance_dates_df = pd.read_sql_query(query, conn, params=params if params else None)
        
        if rebalance_dates_df.empty:
            print("❌ ポートフォリオが見つかりませんでした")
            return 1
        
        rebalance_dates = rebalance_dates_df["rebalance_date"].tolist()
        print(f"✅ {len(rebalance_dates)}個のポートフォリオが見つかりました")
        print(f"   最初: {rebalance_dates[0] if rebalance_dates else 'N/A'}")
        print(f"   最後: {rebalance_dates[-1] if rebalance_dates else 'N/A'}")
        print()
    
    # 各ポートフォリオのパフォーマンスを計算
    results = []
    success_count = 0
    error_count = 0
    
    for i, rebalance_date in enumerate(rebalance_dates, 1):
        print(f"[{i}/{len(rebalance_dates)}] {rebalance_date} のパフォーマンスを計算中...")
        
        try:
            performance = calculate_portfolio_performance(rebalance_date, as_of_date)
            
            if "error" in performance:
                error_count += 1
                print(f"  ❌ エラー: {performance['error']}")
                results.append({
                    "rebalance_date": rebalance_date,
                    "error": performance["error"],
                })
            else:
                # データベースに保存
                save_performance_to_db(performance)
                success_count += 1
                
                total_return = performance.get("total_return_pct")
                topix_return = performance.get("topix_comparison", {}).get("topix_return_pct")
                excess_return = performance.get("topix_comparison", {}).get("excess_return_pct")
                
                if total_return is not None:
                    print(f"  ✅ 成功 (リターン: {total_return:.2f}%)", end="")
                    if topix_return is not None:
                        print(f" | TOPIX: {topix_return:.2f}%", end="")
                    if excess_return is not None:
                        print(f" | 超過: {excess_return:.2f}%", end="")
                    print()
                else:
                    print(f"  ✅ 成功 (リターン: N/A)")
                
                results.append({
                    "rebalance_date": rebalance_date,
                    "as_of_date": performance.get("as_of_date"),
                    "total_return_pct": total_return,
                    "topix_return_pct": topix_return,
                    "excess_return_pct": excess_return,
                })
        
        except Exception as e:
            error_count += 1
            print(f"  ❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "rebalance_date": rebalance_date,
                "error": str(e),
            })
        
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
            if "error" in result:
                print(f"  - {result['rebalance_date']}: {result['error']}")
        print()
    
    # 成功した結果の統計
    if success_count > 0:
        successful_results = [r for r in results if "error" not in r]
        returns = [r["total_return_pct"] for r in successful_results if r.get("total_return_pct") is not None]
        
        if returns:
            print("【パフォーマンス統計】")
            print(f"平均リターン: {sum(returns) / len(returns):.2f}%")
            print(f"最小リターン: {min(returns):.2f}%")
            print(f"最大リターン: {max(returns):.2f}%")
            print()
    
    print("=" * 80)
    
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="既存のポートフォリオに対してパフォーマンス計算のみを実行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # すべてのポートフォリオのパフォーマンスを計算（最新の価格データで評価）
  python -m omanta_3rd.jobs.calculate_all_performance
  
  # 特定の評価日でパフォーマンスを計算
  python -m omanta_3rd.jobs.calculate_all_performance --as-of-date 2025-12-28
  
  # 特定期間のポートフォリオのみ計算
  python -m omanta_3rd.jobs.calculate_all_performance --start 2016-01-01 --end 2025-12-28
        """
    )
    
    parser.add_argument(
        "--as-of-date",
        type=str,
        dest="as_of_date",
        default=None,
        help="評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）",
    )
    parser.add_argument(
        "--start",
        type=str,
        dest="start_date",
        default=None,
        help="開始日（YYYY-MM-DD、この日以降のポートフォリオのみ計算）",
    )
    parser.add_argument(
        "--end",
        type=str,
        dest="end_date",
        default=None,
        help="終了日（YYYY-MM-DD、この日以前のポートフォリオのみ計算）",
    )
    
    args = parser.parse_args()
    
    sys.exit(main(
        as_of_date=args.as_of_date,
        start_date=args.start_date,
        end_date=args.end_date,
    ))

