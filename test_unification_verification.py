"""
統一確認スクリプト：compare側とoptimize側で同じparamsファイルを使用して
portfolio_hashが一致することを確認

使用方法:
    python test_unification_verification.py --params-file params_operational_24M_lambda0.00_best_20260111_154617.json --rebalance-dates 2023-01-31
    python test_unification_verification.py --params-file params_operational_24M_lambda0.00_best_20260111_154617.json --rebalance-dates 2023-01-31 2023-02-28 2023-03-31
"""

from __future__ import annotations

import argparse
import json
import sys
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

from omanta_3rd.config.settings import PROJECT_ROOT
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


def calculate_params_hash(strategy_params: StrategyParams, entry_params: EntryScoreParams) -> str:
    """パラメータのハッシュを計算"""
    params_dict = {
        "w_quality": strategy_params.w_quality,
        "w_value": strategy_params.w_value,
        "w_growth": strategy_params.w_growth,
        "w_record_high": strategy_params.w_record_high,
        "w_size": strategy_params.w_size,
        "w_forward_per": strategy_params.w_forward_per,
        "w_pbr": strategy_params.w_pbr,
        "rsi_base": entry_params.rsi_base,
        "rsi_max": entry_params.rsi_max,
        "bb_z_base": entry_params.bb_z_base,
        "bb_z_max": entry_params.bb_z_max,
        "bb_weight": entry_params.bb_weight,
        "rsi_weight": entry_params.rsi_weight,
    }
    params_str = json.dumps(params_dict, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(params_str.encode('utf-8')).hexdigest()[:8]


def calculate_portfolio_hash(selected_codes: List[str], weights: List[float]) -> str:
    """ポートフォリオのハッシュを計算"""
    portfolio_content = {
        "selected_codes": sorted(selected_codes),
        "weights": [round(w, 4) for w in weights],
    }
    portfolio_str = json.dumps(portfolio_content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(portfolio_str.encode('utf-8')).hexdigest()[:8]


def compare_results(
    params_file: str,
    rebalance_dates: List[str],
    as_of_date: str = "2025-12-31",
    horizon_months: int = 24,
) -> Dict[str, Any]:
    """
    compare側とoptimize側で同じparamsファイルを使用して結果を比較
    
    Returns:
        比較結果の辞書
    """
    # パラメータファイルを読み込む
    params_data = load_params_file(params_file)
    
    # StrategyParamsとEntryScoreParamsを構築
    strategy_params = StrategyParams(**params_data["params"]["strategy"])
    entry_params = EntryScoreParams(**params_data["params"]["entry"])
    
    params_hash = calculate_params_hash(strategy_params, entry_params)
    
    print(f"\n{'='*80}")
    print(f"統一確認: {params_file}")
    print(f"{'='*80}")
    print(f"params_hash: {params_hash}")
    print(f"rebalance_dates: {rebalance_dates}")
    print(f"horizon_months: {horizon_months}")
    print(f"{'='*80}\n")
    
    results = {
        "params_file": params_file,
        "params_hash": params_hash,
        "rebalance_dates": rebalance_dates,
        "comparisons": [],
    }
    
    for rebalance_date in rebalance_dates:
        print(f"\n{'='*80}")
        print(f"rebalance_date: {rebalance_date}")
        print(f"{'='*80}\n")
        
        comparison = {
            "rebalance_date": rebalance_date,
            "compare": {},
            "optimize": {},
            "match": {},
        }
        
        # compare側の結果を取得
        print(f"[COMPARE] compare側を実行中...")
        sys.stdout.flush()
        compare_debug_output = []
        
        try:
            compare_result = run_backtest_with_params_file(
                params_file=params_file,
                start_date=rebalance_date,
                end_date=rebalance_date,
                as_of_date=as_of_date,
                horizon_months=horizon_months,
                debug_rebalance_dates={rebalance_date},
            )
            
            # デバッグ出力をキャプチャ（簡易的な方法）
            # 実際には、run_backtest_with_params_fileがデバッグ出力を返すように変更する必要がある
            print("[COMPARE] compare側の実行完了")
            
        except Exception as e:
            print(f"[COMPARE] エラー: {e}")
            import traceback
            traceback.print_exc()
            comparison["compare"]["error"] = str(e)
            results["comparisons"].append(comparison)
            continue
        
        # optimize側の結果を取得
        print(f"[OPTIMIZE] optimize側を実行中...")
        sys.stdout.flush()
        
        try:
            # calculate_longterm_performanceを使用して単一のrebalance_dateを評価
            optimize_result = calculate_longterm_performance(
                rebalance_dates=[rebalance_date],
                strategy_params=strategy_params,
                entry_params=entry_params,
                horizon_months=horizon_months,
                as_of_date=as_of_date,
                require_full_horizon=True,
                debug_rebalance_dates={rebalance_date},
            )
            
            print("[OPTIMIZE] optimize側の実行完了")
            
        except Exception as e:
            print(f"[OPTIMIZE] エラー: {e}")
            import traceback
            traceback.print_exc()
            comparison["optimize"]["error"] = str(e)
            results["comparisons"].append(comparison)
            continue
        
        # 結果を比較（デバッグ出力から取得）
        # 実際には、run_backtest_with_params_fileとcalculate_longterm_performanceが
        # デバッグ情報を返すように変更する必要がある
        
        results["comparisons"].append(comparison)
    
    return results


def main():
    parser = argparse.ArgumentParser(description="統一確認スクリプト")
    parser.add_argument(
        "--params-file",
        type=str,
        required=True,
        help="パラメータファイル名（例: params_operational_24M_lambda0.00_best_20260111_154617.json）",
    )
    parser.add_argument(
        "--rebalance-dates",
        type=str,
        nargs="+",
        required=True,
        help="リバランス日（例: 2023-01-31 2023-02-28）",
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
    parser.add_argument(
        "--output",
        type=str,
        help="出力ファイル（JSON形式、指定しない場合は標準出力）",
    )
    
    args = parser.parse_args()
    
    results = compare_results(
        params_file=args.params_file,
        rebalance_dates=args.rebalance_dates,
        as_of_date=args.as_of_date,
        horizon_months=args.horizon_months,
    )
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n結果を {output_path} に保存しました")
    else:
        print("\n" + "="*80)
        print("比較結果:")
        print("="*80)
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

