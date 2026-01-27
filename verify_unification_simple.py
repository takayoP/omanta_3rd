"""
統一確認スクリプト（簡易版）：compare側とoptimize側で同じparamsファイルを使用して
portfolio_hashが一致することを確認

このスクリプトは、compare側とoptimize側の両方を実行して、
デバッグ出力（標準出力のJSON）を比較します。

使用方法:
    python verify_unification_simple.py --params-file params_operational_24M_lambda0.00_best_20260111_154617.json --rebalance-date 2023-01-31
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# プロジェクトルートをパスに追加
from omanta_3rd.config.settings import PROJECT_ROOT
sys.path.insert(0, str(PROJECT_ROOT.parent / "src"))

from omanta_3rd.jobs.compare_lambda_penalties import run_backtest_with_params_file
from omanta_3rd.jobs.optimize_longterm import calculate_longterm_performance
from omanta_3rd.jobs.longterm_run import StrategyParams
from omanta_3rd.jobs.optimize import EntryScoreParams
from omanta_3rd.config.params_registry import load_params_by_id_longterm


def load_params_file(params_file: str) -> Dict[str, Any]:
    """パラメータファイルを読み込む"""
    params_path = PROJECT_ROOT / "params" / params_file
    if not params_path.exists():
        raise FileNotFoundError(f"パラメータファイルが見つかりません: {params_path}")
    
    with open(params_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_single_date(
    params_file: str,
    rebalance_date: str,
    as_of_date: str = "2025-12-31",
    horizon_months: int = 24,
) -> Dict[str, Any]:
    """
    単一のrebalance_dateについて、compare側とoptimize側の結果を比較
    
    注意: このスクリプトは、標準出力に出力されるDEBUG JSONを手動で比較することを前提としています。
    実際の比較は、実行後の出力を確認してください。
    """
    # パラメータファイルを読み込む
    params_data = load_params_file(params_file)
    
    # StrategyParamsとEntryScoreParamsを構築
    strategy_params = StrategyParams(**params_data["params"]["strategy"])
    entry_params = EntryScoreParams(**params_data["params"]["entry"])
    
    print(f"\n{'='*80}")
    print(f"統一確認: {params_file}")
    print(f"rebalance_date: {rebalance_date}")
    print(f"horizon_months: {horizon_months}")
    print(f"as_of_date: {as_of_date}")
    print(f"{'='*80}\n")
    
    # compare側を実行
    print(f"\n{'='*80}")
    print(f"[COMPARE] compare側を実行中...")
    print(f"{'='*80}\n")
    
    try:
        compare_result = run_backtest_with_params_file(
            params_file=params_file,
            start_date=rebalance_date,
            end_date=rebalance_date,
            as_of_date=as_of_date,
            horizon_months=horizon_months,
            debug_rebalance_dates={rebalance_date},
        )
        print(f"\n[COMPARE] compare側の実行完了\n")
    except Exception as e:
        print(f"\n[COMPARE] エラー: {e}\n")
        import traceback
        traceback.print_exc()
    
    # optimize側を実行
    print(f"\n{'='*80}")
    print(f"[OPTIMIZE] optimize側を実行中...")
    print(f"{'='*80}\n")
    
    try:
        optimize_result = calculate_longterm_performance(
            rebalance_dates=[rebalance_date],
            strategy_params=strategy_params,
            entry_params=entry_params,
            horizon_months=horizon_months,
            as_of_date=as_of_date,
            require_full_horizon=True,
            debug_rebalance_dates={rebalance_date},
        )
        print(f"\n[OPTIMIZE] optimize側の実行完了\n")
    except Exception as e:
        print(f"\n[OPTIMIZE] エラー: {e}\n")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*80}")
    print(f"実行完了")
    print(f"{'='*80}")
    print(f"\n以下のデバッグ出力を確認してください：")
    print(f"  - [DEBUG_COMPARE] で始まる行（compare側）")
    print(f"  - [DEBUG] で始まる行（optimize側）")
    print(f"\n比較項目：")
    print(f"  - params_hash: 一致する必要があります")
    print(f"  - portfolio_hash: 一致する必要があります（これがゴール）")
    print(f"  - selected_codes: 一致する必要があります")
    print(f"  - weights: 一致する必要があります（等ウェイト）")
    print(f"  - entry_date / exit_date: 一致する必要があります")
    print(f"  - total_return_pct / topix_return_pct: 一致する必要があります")


def main():
    parser = argparse.ArgumentParser(description="統一確認スクリプト（簡易版）")
    parser.add_argument(
        "--params-file",
        type=str,
        required=True,
        help="パラメータファイル名（例: params_operational_24M_lambda0.00_best_20260111_154617.json）",
    )
    parser.add_argument(
        "--rebalance-date",
        type=str,
        required=True,
        help="リバランス日（例: 2023-01-31）",
    )
    parser.add_argument(
        "--as-of-date",
        type=str,
        default="2025-12-31",
        help="評価の打ち切り日（デフォルト: 2025-12-31）",
    )
    parser.add_argument(
        "--horizon-months",
        type=int,
        default=24,
        help="投資ホライズン（月数、デフォルト: 24）",
    )
    
    args = parser.parse_args()
    
    compare_single_date(
        params_file=args.params_file,
        rebalance_date=args.rebalance_date,
        as_of_date=args.as_of_date,
        horizon_months=args.horizon_months,
    )


if __name__ == "__main__":
    main()




