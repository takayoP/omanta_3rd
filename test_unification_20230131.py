"""
統一確認スクリプト：compare側とoptimize側で同じparamsファイルを使用して
portfolio_hashが一致することを確認

使用方法:
    python test_unification_20230131.py
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent / "src"))

from omanta_3rd.config.settings import PROJECT_ROOT
from omanta_3rd.jobs.compare_lambda_penalties import run_backtest_with_params_file
from omanta_3rd.jobs.optimize_longterm import calculate_longterm_performance
from omanta_3rd.jobs.longterm_run import StrategyParams
from omanta_3rd.jobs.optimize import EntryScoreParams


def main():
    params_file = "params_operational_24M_lambda0.00_best_20260111_154617.json"
    rebalance_date = "2023-01-31"
    as_of_date = "2025-12-31"
    horizon_months = 24
    
    # パラメータファイルを読み込む（プロジェクトルート直下）
    params_path = PROJECT_ROOT / params_file
    if not params_path.exists():
        print(f"エラー: パラメータファイルが見つかりません: {params_path}")
        return
    
    with open(params_path, "r", encoding="utf-8") as f:
        params_data = json.load(f)
    
    # パラメータファイルの構造に応じて読み込む
    params = params_data.get("params", {})
    if not params:
        print(f"エラー: パラメータがパラメータファイルに見つかりません")
        return
    
    # StrategyParamsとEntryScoreParamsを構築
    strategy_params = StrategyParams(
        target_min=12,
        target_max=12,
        w_quality=params.get("w_quality", 0.0),
        w_value=params.get("w_value", 0.0),
        w_growth=params.get("w_growth", 0.0),
        w_record_high=params.get("w_record_high", 0.0),
        w_size=params.get("w_size", 0.0),
        w_forward_per=params.get("w_forward_per", 0.0),
        w_pbr=params.get("w_pbr", 0.0),
        roe_min=params.get("roe_min", 0.0),
        liquidity_quantile_cut=params.get("liquidity_quantile_cut", 0.1),
    )
    
    entry_params = EntryScoreParams(
        rsi_base=params.get("rsi_base", 50.0),
        rsi_max=params.get("rsi_max", 70.0),
        bb_z_base=params.get("bb_z_base", 0.0),
        bb_z_max=params.get("bb_z_max", 1.0),
        bb_weight=params.get("bb_weight", 0.5),
        rsi_weight=1.0 - params.get("bb_weight", 0.5),
        rsi_min_width=params.get("rsi_min_width", 20.0),
        bb_z_min_width=params.get("bb_z_min_width", 1.0),
    )
    
    print("="*80)
    print("統一確認: compare側とoptimize側で同じparamsファイルを使用")
    print("="*80)
    print(f"params_file: {params_file}")
    print(f"rebalance_date: {rebalance_date}")
    print(f"horizon_months: {horizon_months}")
    print(f"as_of_date: {as_of_date}")
    print("="*80)
    print()
    
    # compare側を実行
    print("="*80)
    print("[COMPARE] compare側を実行中...")
    print("="*80)
    print()
    
    try:
        compare_result = run_backtest_with_params_file(
            params_path,
            rebalance_date,
            rebalance_date,
            as_of_date,
            require_full_horizon=True,
            debug_rebalance_dates={rebalance_date},
        )
        print()
        print("[COMPARE] compare側の実行完了")
        print()
    except Exception as e:
        print(f"[COMPARE] エラー: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # optimize側を実行
    print("="*80)
    print("[OPTIMIZE] optimize側を実行中...")
    print("="*80)
    print()
    
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
        print()
        print("[OPTIMIZE] optimize側の実行完了")
        print()
    except Exception as e:
        print(f"[OPTIMIZE] エラー: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("="*80)
    print("実行完了")
    print("="*80)
    print()
    print("以下のデバッグ出力を確認してください：")
    print("  - [DEBUG_COMPARE] で始まる行（compare側）")
    print("  - [DEBUG] で始まる行（optimize側）")
    print()
    print("比較項目：")
    print("  - params_hash: 一致する必要があります")
    print("  - portfolio_hash: 一致する必要があります（これがゴール）")
    print("  - selected_codes: 一致する必要があります")
    print("  - weights: 一致する必要があります（等ウェイト）")
    print("  - entry_date / exit_date: 一致する必要があります")
    print("  - total_return_pct / topix_return_pct: 一致する必要があります")


if __name__ == "__main__":
    main()

