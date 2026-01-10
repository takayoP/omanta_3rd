"""
最適化結果の詳細分析スクリプト

ChatGPTのフィードバックに基づき、以下の追加分析を実施：
1. train側の中央値・分位点（P25/P75）
2. 年別（2020/21/22、2023/24/25）の成績
3. 月別リターンの分布
"""

from __future__ import annotations

import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from ..config.settings import PROJECT_ROOT
from ..infra.db import connect_db
from ..backtest.performance import calculate_portfolio_performance


def load_optimization_result(result_file: Path) -> Dict[str, Any]:
    """最適化結果JSONを読み込む"""
    with open(result_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_train_performances(
    study_name: str,
    best_params: Dict[str, Any],
    train_dates: List[str],
    horizon_months: int,
    as_of_date: str,
) -> List[Dict[str, Any]]:
    """
    学習期間の各ポートフォリオのパフォーマンスを取得
    
    注意: これは簡易版で、実際の最適化時のtrain期間のパフォーマンスを再計算する必要がある
    今回は、最適化結果JSONにtrain期間の詳細が含まれていないため、
    実際のtrain期間のリバランス日を特定して再計算する必要がある
    """
    # 実際には、最適化時のtrain期間のリバランス日を特定する必要がある
    # ここでは簡易的に、train_datesを使用
    performances = []
    
    with connect_db() as conn:
        for rebalance_date in train_dates:
            # 評価終了日を計算
            from dateutil.relativedelta import relativedelta
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_end_dt = rebalance_dt + relativedelta(months=horizon_months)
            eval_end_date = eval_end_dt.strftime("%Y-%m-%d")
            
            # as_of_dateと比較（train期間なので、train_end_dateを使用）
            train_end_dt = datetime.strptime("2022-12-31", "%Y-%m-%d")
            if eval_end_dt > train_end_dt:
                continue  # ホライズン未達
            
            # パフォーマンスを計算
            try:
                perf = calculate_portfolio_performance(rebalance_date, eval_end_date)
                if "error" not in perf:
                    performances.append(perf)
            except Exception as e:
                print(f"警告: {rebalance_date}のパフォーマンス計算でエラー: {e}")
    
    return performances


def analyze_performance_distribution(performances: List[Dict[str, Any]]) -> Dict[str, Any]:
    """パフォーマンスの分布を分析"""
    if not performances:
        return {}
    
    # 年率超過リターンを抽出
    excess_returns = []
    for perf in performances:
        topix_comparison = perf.get("topix_comparison", {})
        excess_return = topix_comparison.get("excess_return_pct")
        if excess_return is not None and not pd.isna(excess_return):
            excess_returns.append(excess_return)
    
    if not excess_returns:
        return {}
    
    excess_returns_series = pd.Series(excess_returns)
    
    return {
        "count": len(excess_returns),
        "mean": excess_returns_series.mean(),
        "median": excess_returns_series.median(),
        "std": excess_returns_series.std(),
        "p25": excess_returns_series.quantile(0.25),
        "p75": excess_returns_series.quantile(0.75),
        "min": excess_returns_series.min(),
        "max": excess_returns_series.max(),
    }


def analyze_by_year(performances: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """年別の成績を分析"""
    if not performances:
        return {}
    
    # 年別にグループ化
    by_year = {}
    for perf in performances:
        rebalance_date = perf.get("rebalance_date")
        if not rebalance_date:
            continue
        
        year = rebalance_date[:4]  # YYYY-MM-DDから年を抽出
        
        if year not in by_year:
            by_year[year] = []
        
        topix_comparison = perf.get("topix_comparison", {})
        excess_return = topix_comparison.get("excess_return_pct")
        if excess_return is not None and not pd.isna(excess_return):
            by_year[year].append(excess_return)
    
    # 年別の統計を計算
    result = {}
    for year, returns in by_year.items():
        if not returns:
            continue
        
        returns_series = pd.Series(returns)
        result[year] = {
            "count": len(returns),
            "mean": returns_series.mean(),
            "median": returns_series.median(),
            "std": returns_series.std(),
            "p25": returns_series.quantile(0.25),
            "p75": returns_series.quantile(0.75),
        }
    
    return result


def main():
    """詳細分析を実行"""
    print("=" * 80)
    print("最適化結果の詳細分析")
    print("=" * 80)
    print()
    
    # 分析対象の候補
    candidates = [
        ("operational_24M", "optimization_result_operational_24M_20260109.json", 24),
        ("12M_momentum", "optimization_result_12M_momentum_20260109.json", 12),
        ("12M_reversal", "optimization_result_12M_reversal_20260109.json", 12),
    ]
    
    for params_id, result_file_name, horizon_months in candidates:
        result_file = PROJECT_ROOT / result_file_name
        if not result_file.exists():
            print(f"⚠️  ファイルが見つかりません: {result_file_name}")
            continue
        
        print("=" * 80)
        print(f"【{params_id}】")
        print("=" * 80)
        
        result_data = load_optimization_result(result_file)
        
        # テストデータのパフォーマンス分布
        test_perf = result_data.get("test_performance", {})
        print("\n【テストデータの統計】")
        print(f"  年率超過リターン（平均）: {test_perf.get('mean_annual_excess_return_pct', 'N/A'):.4f}%")
        print(f"  年率超過リターン（中央値）: {test_perf.get('median_annual_excess_return_pct', 'N/A'):.4f}%")
        print(f"  勝率: {test_perf.get('win_rate', 'N/A'):.4f}")
        print(f"  ポートフォリオ数: {test_perf.get('num_portfolios', 'N/A')}")
        
        # 注意: train期間の詳細なパフォーマンスは、最適化結果JSONには含まれていない
        # 実際のtrain期間のリバランス日を特定して再計算する必要がある
        print("\n【注意】")
        print("  train期間の詳細統計（中央値・分位点）は、最適化結果JSONには含まれていません。")
        print("  再計算するには、最適化時のtrain期間のリバランス日を特定する必要があります。")
        print()
    
    print("=" * 80)
    print("分析完了")
    print("=" * 80)
    print()
    print("【次のステップ】")
    print("  1. 最適化時のtrain期間のリバランス日を特定")
    print("  2. train期間の各ポートフォリオのパフォーマンスを再計算")
    print("  3. train期間の中央値・分位点を計算")
    print("  4. 年別の成績を分析")


if __name__ == "__main__":
    main()

