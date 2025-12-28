"""バックテスト実行ジョブ"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from ..backtest.performance import (
    calculate_portfolio_performance,
    calculate_all_portfolios_performance,
    save_performance_to_db,
)
from ..config.settings import PROJECT_ROOT


def main(
    rebalance_date: str | None = None,
    as_of_date: str | None = None,
    output_format: str = "json",
    output_path: str | None = None,
    save_to_db: bool = False,
):
    """
    バックテストを実行
    
    Args:
        rebalance_date: リバランス日（YYYY-MM-DD、Noneの場合はすべてのポートフォリオ）
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）
        output_format: 出力形式（json, csv）
        output_path: 出力パス（Noneの場合は標準出力）
    """
    if rebalance_date:
        # 特定のポートフォリオのパフォーマンスを計算
        perf = calculate_portfolio_performance(rebalance_date, as_of_date)
        
        if "error" in perf:
            print(f"エラー: {perf['error']}")
            return
        
        if output_format == "json":
            output = json.dumps(perf, indent=2, ensure_ascii=False)
        else:
            # CSV形式（TOPIX比較を含む）
            topix_comp = perf.get("topix_comparison", {})
            total_ret = f"{perf['total_return_pct']:.2f}" if perf.get('total_return_pct') is not None else 'N/A'
            topix_ret = f"{topix_comp.get('topix_return_pct'):.2f}" if topix_comp.get('topix_return_pct') is not None else 'N/A'
            excess_ret = f"{topix_comp.get('excess_return_pct'):.2f}" if topix_comp.get('excess_return_pct') is not None else 'N/A'
            avg_ret = f"{perf['avg_return_pct']:.2f}" if perf.get('avg_return_pct') is not None else 'N/A'
            min_ret = f"{perf['min_return_pct']:.2f}" if perf.get('min_return_pct') is not None else 'N/A'
            max_ret = f"{perf['max_return_pct']:.2f}" if perf.get('max_return_pct') is not None else 'N/A'
            output = f"リバランス日,評価日,総リターン(%),TOPIXリターン(%),超過リターン(%),銘柄数,平均リターン(%),最小リターン(%),最大リターン(%)\n"
            output += f"{perf['rebalance_date']},{perf['as_of_date']},"
            output += f"{total_ret},{topix_ret},{excess_ret},"
            output += f"{perf['num_stocks']},"
            output += f"{avg_ret},{min_ret},{max_ret}\n"
        
        if save_to_db:
            save_performance_to_db(perf)
            print("パフォーマンス結果をデータベースに保存しました")
        
        if output_path:
            Path(output_path).write_text(output, encoding="utf-8")
            print(f"結果を {output_path} に保存しました")
        else:
            print(output)
    else:
        # すべてのポートフォリオのパフォーマンスを計算
        results = calculate_all_portfolios_performance(as_of_date)
        
        if output_format == "json":
            output = json.dumps(results, indent=2, ensure_ascii=False)
        else:
            # CSV形式（TOPIX比較を含む）
            output = "リバランス日,評価日,総リターン(%),TOPIXリターン(%),超過リターン(%),銘柄数,平均リターン(%),最小リターン(%),最大リターン(%)\n"
            for perf in results:
                if "error" not in perf:
                    topix_comp = perf.get("topix_comparison", {})
                    total_ret = f"{perf['total_return_pct']:.2f}" if perf.get('total_return_pct') is not None else 'N/A'
                    topix_ret = f"{topix_comp.get('topix_return_pct'):.2f}" if topix_comp.get('topix_return_pct') is not None else 'N/A'
                    excess_ret = f"{topix_comp.get('excess_return_pct'):.2f}" if topix_comp.get('excess_return_pct') is not None else 'N/A'
                    avg_ret = f"{perf['avg_return_pct']:.2f}" if perf.get('avg_return_pct') is not None else 'N/A'
                    min_ret = f"{perf['min_return_pct']:.2f}" if perf.get('min_return_pct') is not None else 'N/A'
                    max_ret = f"{perf['max_return_pct']:.2f}" if perf.get('max_return_pct') is not None else 'N/A'
                    output += f"{perf['rebalance_date']},{perf['as_of_date']},"
                    output += f"{total_ret},{topix_ret},{excess_ret},"
                    output += f"{perf['num_stocks']},"
                    output += f"{avg_ret},{min_ret},{max_ret}\n"
        
        if save_to_db:
            for perf in results:
                if "error" not in perf:
                    save_performance_to_db(perf)
            print("すべてのパフォーマンス結果をデータベースに保存しました")
        
        if output_path:
            Path(output_path).write_text(output, encoding="utf-8")
            print(f"結果を {output_path} に保存しました")
        else:
            print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="バックテスト実行ジョブ")
    parser.add_argument(
        "--rebalance-date",
        type=str,
        help="リバランス日（YYYY-MM-DD、指定しない場合はすべてのポートフォリオ）",
    )
    parser.add_argument(
        "--as-of-date",
        type=str,
        help="評価日（YYYY-MM-DD、指定しない場合は最新の価格データを使用）",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "csv"],
        default="json",
        help="出力形式（デフォルト: json）",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="出力パス（指定しない場合は標準出力）",
    )
    parser.add_argument(
        "--save-to-db",
        action="store_true",
        help="パフォーマンス結果をデータベースに保存",
    )
    
    args = parser.parse_args()
    
    main(
        rebalance_date=args.rebalance_date,
        as_of_date=args.as_of_date,
        output_format=args.format,
        output_path=args.output,
        save_to_db=args.save_to_db,
    )

