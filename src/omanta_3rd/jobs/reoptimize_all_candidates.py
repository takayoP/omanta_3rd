"""
すべての候補パラメータを再最適化（Step 1）

1回のコマンドで以下を実行：
1. operational_24M（長期保有型の24M候補）を再最適化
2. 12M_momentum / 12M_reversal を再最適化
3. 各候補を保存し、registryを更新

使用方法:
    python -m omanta_3rd.jobs.reoptimize_all_candidates --start 2020-01-01 --end 2025-12-31
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Literal

from ..config.settings import PROJECT_ROOT
from ..config.params_registry import load_registry
from .optimize_longterm import main as optimize_longterm_main
from dateutil.relativedelta import relativedelta


def determine_strategy_mode(best_params: Dict[str, Any]) -> Literal["momentum", "reversal"]:
    """
    最適化パラメータから戦略モードを判定（RSIとBBの両方を考慮）
    
    Args:
        best_params: 最適化されたパラメータ
    
    Returns:
        "momentum" または "reversal"
    """
    rsi_base = best_params.get("rsi_base", 50.0)
    rsi_max = best_params.get("rsi_max", 50.0)
    bb_z_base = best_params.get("bb_z_base", 0.0)
    bb_z_max = best_params.get("bb_z_max", 0.0)
    bb_weight = best_params.get("bb_weight", 0.5)
    rsi_weight = 1.0 - bb_weight
    
    # RSIの方向を判定
    # rsi_max > rsi_base なら順張り（momentum = +1）
    # rsi_max < rsi_base なら逆張り（reversal = -1）
    rsi_direction = 1.0 if rsi_max > rsi_base else -1.0
    
    # BB Z-scoreの方向を判定
    # bb_z_max > bb_z_base なら順張り（momentum = +1）
    # bb_z_max < bb_z_base なら逆張り（reversal = -1）
    bb_direction = 1.0 if bb_z_max > bb_z_base else -1.0
    
    # 重み付けスコアを計算
    # 正の値ならmomentum、負の値ならreversal
    weighted_score = (rsi_direction * rsi_weight) + (bb_direction * bb_weight)
    
    if weighted_score > 0:
        return "momentum"
    else:
        return "reversal"


def save_params_file(
    result_data: Dict[str, Any],
    params_id: str,
    horizon_months: int,
    strategy_mode: Literal["momentum", "reversal"],
    version: Optional[str] = None,
) -> Path:
    """
    最適化結果をパラメータファイルとして保存
    
    Args:
        result_data: 最適化結果データ
        params_id: パラメータID
        horizon_months: 投資ホライズン（月数）
        strategy_mode: 戦略モード
        version: バージョン（Noneの場合は自動生成）
    
    Returns:
        保存されたファイルパス
    """
    if version is None:
        version = datetime.now().strftime("%Y%m%d")
    
    # ファイル名を決定
    filename = f"params_{params_id}_{version}.json"
    filepath = PROJECT_ROOT / filename
    
    # パラメータデータを構築
    normalized_params = result_data["normalized_params"]
    test_perf = result_data["test_performance"]
    
    params_data = {
        "metadata": {
            "horizon_months": horizon_months,
            "strategy_type": "operational" if params_id == "operational_24M" else "research",
            "strategy_mode": strategy_mode,
            "source_fold": "reoptimized",
            "source_test_period": f"{result_data['start_date']} to {result_data['end_date']}",
            "source_performance": {
                "ann_excess_mean": test_perf["mean_annual_excess_return_pct"],
                "win_rate": test_perf["win_rate"],
                "n_portfolios": test_perf["num_portfolios"],
            },
            "description": f"{horizon_months}Mホライズン・{strategy_mode}モード。require_full_horizon=Trueで再最適化。",
            "created_at": datetime.now().isoformat(),
            "recommended_for": "operational_use" if params_id == "operational_24M" else "regime_switching",
            "version": version,
        },
        "params": {
            "w_quality": normalized_params["w_quality"],
            "w_growth": normalized_params["w_growth"],
            "w_record_high": normalized_params["w_record_high"],
            "w_size": normalized_params["w_size"],
            "w_value": normalized_params["w_value"],
            "w_forward_per": normalized_params["w_forward_per"],
            "w_pbr": normalized_params["w_pbr"],
            "roe_min": normalized_params["roe_min"],
            "bb_weight": normalized_params["bb_weight"],
            "liquidity_quantile_cut": normalized_params["liquidity_quantile_cut"],
            "rsi_base": normalized_params["rsi_base"],
            "rsi_max": normalized_params["rsi_max"],
            "bb_z_base": normalized_params["bb_z_base"],
            "bb_z_max": normalized_params["bb_z_max"],
            "rsi_min_width": normalized_params["rsi_min_width"],
            "bb_z_min_width": normalized_params["bb_z_min_width"],
        },
    }
    
    # ファイルに保存
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(params_data, f, indent=2, ensure_ascii=False)
    
    print(f"パラメータファイルを保存: {filepath}")
    return filepath


def update_registry(
    params_id: str,
    params_file_path: Path,
    horizon_months: int,
    strategy_mode: Literal["momentum", "reversal"],
    version: Optional[str] = None,
) -> None:
    """
    レジストリを更新
    
    Args:
        params_id: パラメータID
        params_file_path: パラメータファイルパス
        horizon_months: 投資ホライズン（月数）
        strategy_mode: 戦略モード
        version: バージョン
    """
    registry_path = PROJECT_ROOT / "config" / "params_registry_longterm.json"
    
    # レジストリを読み込む
    registry = load_registry()
    
    # 相対パスに変換
    if params_file_path.is_absolute():
        rel_path = params_file_path.relative_to(PROJECT_ROOT)
    else:
        rel_path = params_file_path
    
    # エントリを更新または追加
    registry[params_id] = {
        "horizon_months": horizon_months,
        "role": "operational" if params_id == "operational_24M" else "research",
        "mode": strategy_mode,
        "source": f"reoptimized_{version or datetime.now().strftime('%Y%m%d')}",
        "params_file_path": str(rel_path),
        "notes": f"{horizon_months}Mホライズン・{strategy_mode}モード。require_full_horizon=Trueで再最適化。",
    }
    
    # レジストリを保存
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"レジストリを更新: {registry_path}")


def optimize_and_save(
    params_id: str,
    horizon_months: int,
    study_type: Literal["A", "B", "C"],
    start_date: str,
    end_date: str,
    n_trials: int = 200,
    n_jobs: int = -1,
    bt_workers: int = -1,
    version: Optional[str] = None,
    as_of_date: Optional[str] = None,
    train_end_date: Optional[str] = None,
    lambda_penalty: float = 0.0,
) -> Dict[str, Any]:
    """
    最適化を実行し、結果を保存
    
    Args:
        params_id: パラメータID
        horizon_months: 投資ホライズン（月数）
        study_type: Studyタイプ
        start_date: 開始日
        end_date: 終了日
        n_trials: 試行回数
        n_jobs: trial並列数
        bt_workers: バックテスト並列数
        version: バージョン
        as_of_date: 評価の打ち切り日（YYYY-MM-DD、Noneの場合はend_dateを使用）
        train_end_date: 学習期間の終了日（YYYY-MM-DD、Noneの場合はtrain_ratioを使用）
        lambda_penalty: 下振れ罰の係数λ（デフォルト: 0.0）
        
    Returns:
        最適化結果データ
    """
    print("=" * 80)
    print(f"【{params_id} の最適化を開始】")
    print("=" * 80)
    print(f"ホライズン: {horizon_months}M")
    print(f"Studyタイプ: {study_type}")
    print(f"期間: {start_date} ～ {end_date}")
    print(f"試行回数: {n_trials}")
    print(f"下振れ罰係数λ: {lambda_penalty}")
    print("=" * 80)
    print()
    
    # 最適化を実行（内部で最適化結果JSONを保存）
    study_name = f"{params_id}_{version or datetime.now().strftime('%Y%m%d')}"
    
    # 一時的に標準出力をキャプチャする必要があるが、ここでは直接呼び出す
    # 注意: optimize_longterm_mainは最適化結果JSONを保存するが、
    #       そのJSONファイルを読み込んでパラメータファイルを作成する必要がある
    
    # 最適化を実行
    optimize_longterm_main(
        start_date=start_date,
        end_date=end_date,
        study_type=study_type,
        n_trials=n_trials,
        study_name=study_name,
        n_jobs=n_jobs,
        bt_workers=bt_workers,
        cost_bps=0.0,
        storage=None,
        no_db_write=False,
        cache_dir="cache/features",
        train_ratio=0.8,
        random_seed=42,
        save_params=None,  # 後で処理
        params_id=params_id,
        version=version,
        horizon_months=horizon_months,
        strategy_mode=None,  # 自動判定
        as_of_date=as_of_date,
        train_end_date=train_end_date,
        lambda_penalty=lambda_penalty,
    )
    
    # 最適化結果JSONを読み込む
    result_file = PROJECT_ROOT / f"optimization_result_{study_name}.json"
    if not result_file.exists():
        raise FileNotFoundError(f"最適化結果ファイルが見つかりません: {result_file}")
    
    with open(result_file, "r", encoding="utf-8") as f:
        result_data = json.load(f)
    
    # 戦略モードを判定
    best_params = result_data["best_trial"]["params"]
    strategy_mode = determine_strategy_mode(best_params)
    
    print(f"戦略モード: {strategy_mode}")
    print()
    
    # パラメータファイルを保存
    params_file_path = save_params_file(
        result_data,
        params_id,
        horizon_months,
        strategy_mode,
        version,
    )
    
    # レジストリを更新
    update_registry(
        params_id,
        params_file_path,
        horizon_months,
        strategy_mode,
        version,
    )
    
    print()
    print(f"✓ {params_id} の最適化と保存が完了しました")
    print()
    
    return result_data


def main(
    start_date: str,
    end_date: str,
    n_trials: int = 200,
    n_jobs: int = -1,
    bt_workers: int = -1,
    version: Optional[str] = None,
    skip_24m: bool = False,
    skip_12m: bool = False,
    as_of_date: Optional[str] = None,
    train_end_date: Optional[str] = None,
    lambda_penalty: float = 0.0,
):
    """
    すべての候補パラメータを再最適化
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD、24Mの場合は自動調整される可能性あり）
        n_trials: 試行回数（デフォルト: 200）
        n_jobs: trial並列数（-1でCPU数）
        bt_workers: バックテスト並列数（-1で自動）
        version: バージョン（Noneの場合は自動生成）
        skip_24m: 24Mの最適化をスキップ
        skip_12m: 12Mの最適化をスキップ
        as_of_date: 評価の打ち切り日（YYYY-MM-DD、Noneの場合はend_dateを使用）
        train_end_date: 学習期間の終了日（YYYY-MM-DD、Noneの場合は自動計算）
                        **重要**: 時系列リーク対策のため、明示的に指定することを推奨
    """
    if version is None:
        version = datetime.now().strftime("%Y%m%d")
    
    # as_of_dateが指定されていない場合、end_dateを使用
    if as_of_date is None:
        as_of_date = end_date
    
    # Step 3: 24Mと12Mで異なるrebalance_end_dateを使用（評価窓を完走させるため）
    # 24Mの最適化は、24Mホライズンが完走できるようにrebalance_end_dateを早める
    # 重要: rebalance_end_date（リバランス日の取得範囲）とas_of_date（評価の打ち切り日）は分離する
    from dateutil.relativedelta import relativedelta
    rebalance_end_date_24m = end_date
    if not skip_24m:
        # 24Mホライズンが完走できるように、end_dateから24ヶ月前を計算
        # これがリバランス日の取得範囲（rebalance_end_date）になる
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        end_dt_24m = end_dt - relativedelta(months=24)
        rebalance_end_date_24m = end_dt_24m.strftime("%Y-%m-%d")
        print(f"24M最適化用のrebalance_end_dateを調整: {end_date} → {rebalance_end_date_24m} (24Mホライズン完走のため)")
        print(f"  24Mのas_of_date（評価の打ち切り日）: {as_of_date} (元のend_dateを使用)")
    
    # train_end_dateが指定されていない場合、自動計算（時系列リーク対策）
    if train_end_date is None:
        # デフォルト: 2020-2022をtrain、2023をval、2024以降をholdout
        train_end_date = "2022-12-31"
        print(f"train_end_dateが指定されていません。デフォルト値を使用: {train_end_date}")
        print(f"  train: {start_date} ～ {train_end_date}")
        print("  val: 2023-01-01 ～ 2023-12-31")
        print(f"  holdout: 2024-01-01 ～ {end_date}")
    
    print("=" * 80)
    print("すべての候補パラメータを再最適化（Step 1）")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    if not skip_24m:
        print(f"  24M用rebalance_end_date: {rebalance_end_date_24m}")
        print(f"  24M用as_of_date（評価の打ち切り日）: {as_of_date}")
    print(f"  12M用rebalance_end_date: {end_date}")
    print(f"  12M用as_of_date（評価の打ち切り日）: {as_of_date}")
    print(f"学習期間終了日: {train_end_date}")
    print(f"試行回数: {n_trials}")
    print(f"バージョン: {version}")
    print("=" * 80)
    print()
    
    results = {}
    
    # 1. operational_24Mを最適化
    if not skip_24m:
        results["operational_24M"] = optimize_and_save(
            params_id="operational_24M",
            horizon_months=24,
            study_type="C",  # 広範囲探索
            start_date=start_date,
            end_date=rebalance_end_date_24m,  # 24M用のリバランス日取得範囲
            n_trials=n_trials,
            n_jobs=n_jobs,
            bt_workers=bt_workers,
            version=version,
            as_of_date=as_of_date,  # 評価の打ち切り日（元のend_dateを使用）
            train_end_date=train_end_date,
            lambda_penalty=lambda_penalty,
        )
    
    # 2. 12M_momentumを最適化
    if not skip_12m:
        results["12M_momentum"] = optimize_and_save(
            params_id="12M_momentum",
            horizon_months=12,
            study_type="A",  # BB寄り・低ROE閾値（momentum向け）
            start_date=start_date,
            end_date=end_date,  # 12Mはそのまま
            n_trials=n_trials,
            n_jobs=n_jobs,
            bt_workers=bt_workers,
            version=version,
            as_of_date=as_of_date,
            train_end_date=train_end_date,
            lambda_penalty=lambda_penalty,
        )
    
    # 3. 12M_reversalを最適化
    if not skip_12m:
        results["12M_reversal"] = optimize_and_save(
            params_id="12M_reversal",
            horizon_months=12,
            study_type="B",  # Value寄り・ROE閾値やや高め（reversal向け）
            start_date=start_date,
            end_date=end_date,  # 12Mはそのまま
            n_trials=n_trials,
            n_jobs=n_jobs,
            bt_workers=bt_workers,
            version=version,
            as_of_date=as_of_date,
            train_end_date=train_end_date,
            lambda_penalty=lambda_penalty,
        )
    
    print("=" * 80)
    print("すべての最適化が完了しました")
    print("=" * 80)
    print()
    print("【保存されたファイル】")
    for params_id, result_data in results.items():
        print(f"  - {params_id}: optimization_result_{params_id}_{version}.json")
        print(f"    params_{params_id}_{version}.json")
    print()
    print("【レジストリ】")
    print(f"  config/params_registry_longterm.json が更新されました")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="すべての候補パラメータを再最適化（Step 1）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--start", type=str, required=True, help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, required=True, help="終了日（YYYY-MM-DD）")
    parser.add_argument("--n-trials", type=int, default=200, help="試行回数（デフォルト: 200）")
    parser.add_argument("--n-jobs", type=int, default=-1, help="trial並列数（-1でCPU数）")
    parser.add_argument("--bt-workers", type=int, default=-1, help="バックテスト並列数（-1で自動）")
    parser.add_argument("--version", type=str, default=None, help="バージョン（Noneの場合は自動生成）")
    parser.add_argument("--skip-24m", action="store_true", help="24Mの最適化をスキップ")
    parser.add_argument("--skip-12m", action="store_true", help="12Mの最適化をスキップ")
    parser.add_argument("--as-of-date", type=str, default=None, dest="as_of_date", help="評価の打ち切り日（YYYY-MM-DD、Noneの場合はend_dateを使用）")
    parser.add_argument("--train-end-date", type=str, default=None, dest="train_end_date", help="学習期間の終了日（YYYY-MM-DD、Noneの場合は2022-12-31）")
    parser.add_argument("--lambda-penalty", type=float, default=0.0, dest="lambda_penalty", help="下振れ罰の係数λ（デフォルト: 0.0）")
    
    args = parser.parse_args()
    
    main(
        start_date=args.start,
        end_date=args.end,
        n_trials=args.n_trials,
        n_jobs=args.n_jobs,
        bt_workers=args.bt_workers,
        version=args.version,
        skip_24m=args.skip_24m,
        skip_12m=args.skip_12m,
        as_of_date=args.as_of_date,
        train_end_date=args.train_end_date,
        lambda_penalty=args.lambda_penalty,
    )

