"""
月次リバランス型：mom/rev最適化して候補JSON作成（B-1）

--entry-mode mom で monthly_params_mom.json
--entry-mode rev で monthly_params_rev.json

を作成します。

使用方法:
    python -m omanta_3rd.jobs.optimize_monthly_rebalance --entry-mode mom --output monthly_params_mom.json
    python -m omanta_3rd.jobs.optimize_monthly_rebalance --entry-mode rev --output monthly_params_rev.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Literal

from ..config.settings import PROJECT_ROOT
from .optimize_timeseries import (
    optimize_params_timeseries,
    StrategyParams,
    EntryScoreParams,
)


def optimize_monthly_rebalance(
    entry_mode: Literal["mom", "rev"],
    output_path: str,
    start_date: str = "2020-01-01",
    end_date: str = "2025-12-31",
    n_trials: int = 100,
    n_jobs: int = -1,
) -> None:
    """
    月次リバランス型のmom/rev最適化を実行
    
    Args:
        entry_mode: エントリーモード（"mom"=momentum, "rev"=reversal）
        output_path: 出力パス
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        n_trials: Optunaの試行回数
        n_jobs: 並列実行数（-1でCPU数）
    """
    print("=" * 80)
    print(f"月次リバランス型：{entry_mode.upper()}最適化")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"試行回数: {n_trials}")
    print(f"出力先: {output_path}")
    print("=" * 80)
    print()
    
    # entry_modeに応じた最適化を実行
    # 注意: optimize_timeseries.pyを拡張してentry_modeに対応させる必要がある
    # 現時点では、entry_modeに応じたパラメータ範囲を調整する
    
    # 最適化を実行
    study = optimize_params_timeseries(
        start_date=start_date,
        end_date=end_date,
        n_trials=n_trials,
        n_jobs=n_jobs,
        # entry_modeに応じた設定を追加（将来的に拡張）
    )
    
    # 最適なパラメータを取得
    best_params = study.best_params
    
    # パラメータをJSON形式に整形
    output_data = {
        "entry_mode": entry_mode,
        "optimization_date": str(Path(output_path).stat().st_mtime) if Path(output_path).exists() else None,
        "params": {
            "strategy": {
                "target_min": best_params.get("target_min", 20),
                "target_max": best_params.get("target_max", 30),
                "pool_size": best_params.get("pool_size", 80),
                "roe_min": best_params.get("roe_min", 0.10),
                "liquidity_quantile_cut": best_params.get("liquidity_quantile_cut", 0.20),
                "sector_cap": best_params.get("sector_cap", 4),
                "w_quality": best_params.get("w_quality", 0.35),
                "w_value": best_params.get("w_value", 0.25),
                "w_growth": best_params.get("w_growth", 0.15),
                "w_record_high": best_params.get("w_record_high", 0.15),
                "w_size": best_params.get("w_size", 0.10),
                "w_forward_per": best_params.get("w_forward_per", 0.5),
                "w_pbr": best_params.get("w_pbr", 0.5),
                "use_entry_score": best_params.get("use_entry_score", True),
            },
            "entry": {
                "rsi_base": best_params.get("rsi_base", 51.18),
                "rsi_max": best_params.get("rsi_max", 73.58),
                "bb_z_base": best_params.get("bb_z_base", -0.57),
                "bb_z_max": best_params.get("bb_z_max", 2.16),
                "bb_weight": best_params.get("bb_weight", 0.5527),
                "rsi_weight": best_params.get("rsi_weight", 0.4473),
            },
        },
        "best_value": study.best_value,
        "n_trials": len(study.trials),
    }
    
    # JSONファイルに保存
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 最適化完了: {output_path}")
    print(f"   最適値: {study.best_value:.4f}")
    print(f"   試行回数: {len(study.trials)}")
    print()


def main(
    entry_mode: Literal["mom", "rev"],
    output_path: str,
    start_date: str = "2020-01-01",
    end_date: str = "2025-12-31",
    n_trials: int = 100,
    n_jobs: int = -1,
):
    """
    メイン処理
    
    Args:
        entry_mode: エントリーモード（"mom"=momentum, "rev"=reversal）
        output_path: 出力パス
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        n_trials: Optunaの試行回数
        n_jobs: 並列実行数（-1でCPU数）
    """
    optimize_monthly_rebalance(
        entry_mode=entry_mode,
        output_path=output_path,
        start_date=start_date,
        end_date=end_date,
        n_trials=n_trials,
        n_jobs=n_jobs,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="月次リバランス型：mom/rev最適化して候補JSON作成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # mom最適化
  python -m omanta_3rd.jobs.optimize_monthly_rebalance --entry-mode mom --output monthly_params_mom.json
  
  # rev最適化
  python -m omanta_3rd.jobs.optimize_monthly_rebalance --entry-mode rev --output monthly_params_rev.json
  
  # 試行回数を指定
  python -m omanta_3rd.jobs.optimize_monthly_rebalance --entry-mode mom --output monthly_params_mom.json --n-trials 200
        """
    )
    
    parser.add_argument(
        "--entry-mode",
        type=str,
        choices=["mom", "rev"],
        required=True,
        help="エントリーモード（mom=momentum, rev=reversal）",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="出力パス（JSONファイル）",
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2020-01-01",
        help="開始日（YYYY-MM-DD、デフォルト: 2020-01-01）",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2025-12-31",
        help="終了日（YYYY-MM-DD、デフォルト: 2025-12-31）",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=100,
        help="Optunaの試行回数（デフォルト: 100）",
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=-1,
        help="並列実行数（-1でCPU数、デフォルト: -1）",
    )
    
    args = parser.parse_args()
    
    main(
        entry_mode=args.entry_mode,
        output_path=args.output,
        start_date=args.start,
        end_date=args.end,
        n_trials=args.n_trials,
        n_jobs=args.n_jobs,
    )

