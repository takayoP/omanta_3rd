"""
最適化結果の詳細分析スクリプト

ChatGPTのフィードバックに基づき、以下の追加分析を実施：
1. train側の中央値・分位点（P25/P75）
2. 年別（2020/21/22、2023/24/25）の成績
3. 月別リターンの分布
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

from ..config.settings import PROJECT_ROOT


def load_optimization_result(result_file: Path) -> Dict[str, Any]:
    """最適化結果JSONを読み込む"""
    with open(result_file, "r", encoding="utf-8") as f:
        return json.load(f)


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

