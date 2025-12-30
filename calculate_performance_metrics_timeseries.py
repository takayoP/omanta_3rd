"""
ポートフォリオの運用評価指標を計算（時系列版）

時系列P/L計算を使用して、標準的なバックテスト指標を計算します。
月次リバランス戦略として、ti→ti+1の月次リターン系列から指標を計算します。

【既存版との違い】
- 既存版（calculate_performance_metrics.py）: 各リバランス日から最終日までの累積リターンを計算
- 時系列版（本ファイル）: 各リバランス日から次のリバランス日までの月次リターンを計算
"""

from __future__ import annotations

import sys
from typing import Dict, Any, Optional
import json
from pathlib import Path

from omanta_3rd.backtest.timeseries import calculate_timeseries_returns
from omanta_3rd.backtest.metrics import (
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_profit_factor_timeseries,
    calculate_win_rate_timeseries,
    calculate_cagr,
    calculate_volatility_timeseries,
)


def calculate_performance_metrics_timeseries(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    cost_bps: float = 0.0,
) -> Dict[str, Any]:
    """
    ポートフォリオの運用評価指標を計算（時系列版）
    
    Args:
        start_date: 開始日（YYYY-MM-DD、Noneの場合は全期間）
        end_date: 終了日（YYYY-MM-DD、Noneの場合は最新）
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
    
    Returns:
        運用評価指標の辞書
    """
    print("=" * 80)
    print("運用評価指標の計算（時系列版）")
    print("=" * 80)
    
    # デフォルトの日付範囲を設定
    if start_date is None:
        start_date = "2021-01-01"
    if end_date is None:
        from omanta_3rd.infra.db import connect_db
        import pandas as pd
        with connect_db() as conn:
            latest_date_df = pd.read_sql_query(
                "SELECT MAX(date) as max_date FROM prices_daily",
                conn
            )
            if not latest_date_df.empty and pd.notna(latest_date_df["max_date"].iloc[0]):
                end_date = str(latest_date_df["max_date"].iloc[0])
            else:
                end_date = "2025-12-31"
    
    print(f"期間: {start_date} ～ {end_date}")
    print(f"取引コスト: {cost_bps} bps")
    print()
    
    # 時系列P/Lを計算
    print("時系列P/Lを計算中...")
    timeseries_data = calculate_timeseries_returns(
        start_date=start_date,
        end_date=end_date,
        rebalance_dates=None,  # 自動取得
        cost_bps=cost_bps,
    )
    
    monthly_returns = timeseries_data["monthly_returns"]
    monthly_excess_returns = timeseries_data["monthly_excess_returns"]
    equity_curve = timeseries_data["equity_curve"]
    dates = timeseries_data["dates"]
    portfolio_details = timeseries_data["portfolio_details"]
    
    if not monthly_returns:
        print("❌ 月次リターンデータがありません")
        return {}
    
    print(f"リバランス日数: {len(dates)}")
    print(f"月次リターン数: {len(monthly_returns)}")
    print()
    
    # 指標を計算
    print("指標を計算中...")
    
    # 基本統計
    mean_return = sum(monthly_returns) / len(monthly_returns) if monthly_returns else 0.0
    mean_excess_return = sum(monthly_excess_returns) / len(monthly_excess_returns) if monthly_excess_returns else 0.0
    
    # エクイティカーブから計算
    max_dd = calculate_max_drawdown(equity_curve)
    cagr = calculate_cagr(equity_curve, len(monthly_returns))
    volatility = calculate_volatility_timeseries(monthly_returns, annualize=True)
    
    # リスク調整後リターン
    sharpe = calculate_sharpe_ratio(
        monthly_returns,
        monthly_excess_returns,
        risk_free_rate=0.0,
        annualize=True,
    )
    sortino = calculate_sortino_ratio(
        monthly_returns,
        monthly_excess_returns,
        risk_free_rate=0.0,
        annualize=True,
    )
    calmar = calculate_calmar_ratio(equity_curve, monthly_returns)
    
    # 勝率・Profit Factor
    win_rate = calculate_win_rate_timeseries(
        monthly_returns,
        use_excess=True,
        monthly_excess_returns=monthly_excess_returns,
    )
    profit_factor = calculate_profit_factor_timeseries(monthly_returns, equity_curve)
    
    # 結果をまとめる
    result = {
        "calculation_method": "timeseries",
        "description": "月次リバランス戦略として、ti→ti+1の月次リターン系列から計算",
        "period": {
            "start_date": start_date,
            "end_date": end_date,
            "num_rebalance_dates": len(dates),
            "num_monthly_returns": len(monthly_returns),
        },
        "cost_bps": cost_bps,
        "equity_curve": equity_curve,
        "monthly_returns": [r * 100.0 for r in monthly_returns],  # %換算
        "monthly_excess_returns": [r * 100.0 for r in monthly_excess_returns],  # %換算
        "metrics": {
            # リターン指標
            "cagr": cagr * 100.0 if cagr is not None else None,  # %換算
            "mean_return": mean_return * 100.0,  # %換算
            "mean_excess_return": mean_excess_return * 100.0,  # %換算
            "volatility": volatility * 100.0 if volatility is not None else None,  # %換算
            
            # リスク指標
            "max_drawdown": max_dd * 100.0,  # %換算
            
            # リスク調整後リターン
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            
            # 勝率・Profit Factor
            "win_rate": win_rate,
            "profit_factor": profit_factor,
        },
        "portfolio_details": portfolio_details,
    }
    
    # 結果を表示
    print("=" * 80)
    print("計算結果")
    print("=" * 80)
    print(f"CAGR: {result['metrics']['cagr']:.2f}%" if result['metrics']['cagr'] is not None else "CAGR: N/A")
    print(f"平均リターン: {result['metrics']['mean_return']:.2f}%")
    print(f"平均超過リターン: {result['metrics']['mean_excess_return']:.2f}%")
    print(f"ボラティリティ: {result['metrics']['volatility']:.2f}%" if result['metrics']['volatility'] is not None else "ボラティリティ: N/A")
    print(f"最大ドローダウン: {result['metrics']['max_drawdown']:.2f}%")
    print(f"シャープレシオ: {result['metrics']['sharpe_ratio']:.2f}" if result['metrics']['sharpe_ratio'] is not None else "シャープレシオ: N/A")
    print(f"ソルティノレシオ: {result['metrics']['sortino_ratio']:.2f}" if result['metrics']['sortino_ratio'] is not None else "ソルティノレシオ: N/A")
    print(f"カルマーレシオ: {result['metrics']['calmar_ratio']:.2f}" if result['metrics']['calmar_ratio'] is not None else "カルマーレシオ: N/A")
    print(f"勝率: {result['metrics']['win_rate']*100:.2f}%" if result['metrics']['win_rate'] is not None else "勝率: N/A")
    print(f"プロフィットファクタ: {result['metrics']['profit_factor']:.2f}" if result['metrics']['profit_factor'] is not None else "プロフィットファクタ: N/A")
    print()
    
    return result


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ポートフォリオの運用評価指標を計算（時系列版）")
    parser.add_argument("--start", type=str, help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, help="終了日（YYYY-MM-DD）")
    parser.add_argument("--cost", type=float, default=0.0, help="取引コスト（bps、デフォルト: 0.0）")
    parser.add_argument("--output", type=str, help="出力ファイルパス（JSON形式）")
    
    args = parser.parse_args()
    
    # 指標を計算
    result = calculate_performance_metrics_timeseries(
        start_date=args.start,
        end_date=args.end,
        cost_bps=args.cost,
    )
    
    if not result:
        print("❌ 指標の計算に失敗しました")
        sys.exit(1)
    
    # 結果を保存
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"結果を {output_path} に保存しました")
    else:
        # デフォルトの出力ファイル名
        output_path = Path("performance_metrics_timeseries.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"結果を {output_path} に保存しました")


if __name__ == "__main__":
    main()

