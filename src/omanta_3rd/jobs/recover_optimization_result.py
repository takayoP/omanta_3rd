"""
最適化結果をOptuna studyから復元するスクリプト

エラーでJSON保存まで到達しなかった場合に、studyから結果を復元します。
"""

from __future__ import annotations

import json
import optuna
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from ..config.settings import PROJECT_ROOT


def recover_result_from_study(
    study_name: str,
    study_type: str,
    start_date: str,
    end_date: str,
    n_trials: int,
    train_ratio: float,
    random_seed: int,
    cost_bps: float,
    horizon_months: int,
    storage: str | None = None,
) -> Dict[str, Any]:
    """
    Optuna studyから最適化結果を復元
    
    Args:
        study_name: スタディ名
        study_type: Studyタイプ（"A", "B", "C"）
        start_date: 開始日
        end_date: 終了日
        n_trials: 試行回数
        train_ratio: 学習データの割合
        random_seed: ランダムシード
        cost_bps: 取引コスト
        horizon_months: 投資ホライズン（月数）
        storage: ストレージパス（Noneの場合は自動生成）
    
    Returns:
        最適化結果データ
    """
    # ストレージの設定
    if storage is None:
        storage = f"sqlite:///optuna_{study_name}.db"
    
    # studyを読み込む
    study = optuna.load_study(
        study_name=study_name,
        storage=storage,
    )
    
    print(f"Study '{study_name}' を読み込みました")
    print(f"  総試行数: {len(study.trials)}")
    print(f"  完了試行数: {len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE])}")
    print(f"  最良値: {study.best_value:.4f}%")
    print()
    
    # 最良パラメータを取得
    best_trial = study.best_trial
    best_params = best_trial.params
    
    # normalized_paramsを計算
    w_quality = best_params["w_quality"]
    w_value = best_params["w_value"]
    w_growth = best_params["w_growth"]
    w_record_high = best_params["w_record_high"]
    w_size = best_params["w_size"]
    
    # 正規化（合計が1になるように）
    total = w_quality + w_value + w_growth + w_record_high + w_size
    w_quality /= total
    w_value /= total
    w_growth /= total
    w_record_high /= total
    w_size /= total
    
    # 結果データを構築
    result_data = {
        "study_name": study_name,
        "study_type": study_type,
        "start_date": start_date,
        "end_date": end_date,
        "n_trials": n_trials,
        "train_ratio": train_ratio,
        "random_seed": random_seed,
        "cost_bps": cost_bps,
        "best_trial": {
            "number": best_trial.number,
            "value": study.best_value,
            "params": best_params,
        },
        "train_performance": {
            "mean_annual_excess_return_pct": study.best_value,
        },
        "test_performance": {
            # テストデータでの評価は実行していないため、空にする
            "mean_annual_excess_return_pct": None,
            "median_annual_excess_return_pct": None,
            "mean_annual_return_pct": None,
            "median_annual_return_pct": None,
            "cumulative_return_pct": None,
            "mean_excess_return_pct": None,
            "win_rate": None,
            "num_portfolios": None,
            "mean_holding_years": None,
        },
        "normalized_params": {
            "w_quality": w_quality,
            "w_value": w_value,
            "w_growth": w_growth,
            "w_record_high": w_record_high,
            "w_size": w_size,
            "w_forward_per": best_params["w_forward_per"],
            "w_pbr": 1.0 - best_params["w_forward_per"],
            "roe_min": best_params["roe_min"],
            "liquidity_quantile_cut": best_params["liquidity_quantile_cut"],
            "rsi_base": best_params["rsi_base"],
            "rsi_max": best_params["rsi_max"],
            "bb_z_base": best_params["bb_z_base"],
            "bb_z_max": best_params["bb_z_max"],
            "bb_weight": best_params["bb_weight"],
            "rsi_weight": 1.0 - best_params["bb_weight"],
            "rsi_min_width": 10.0,  # 固定値
            "bb_z_min_width": 0.5,  # 固定値
        },
    }
    
    return result_data


def main():
    """operational_24Mの結果を復元"""
    study_name = "operational_24M_20260109"
    study_type = "C"
    start_date = "2020-01-01"
    end_date = "2023-12-31"  # 24M用のrebalance_end_date
    n_trials = 200
    train_ratio = 0.8
    random_seed = 42
    cost_bps = 0.0
    horizon_months = 24
    
    print("=" * 80)
    print("最適化結果の復元")
    print("=" * 80)
    print(f"Study名: {study_name}")
    print()
    
    try:
        result_data = recover_result_from_study(
            study_name=study_name,
            study_type=study_type,
            start_date=start_date,
            end_date=end_date,
            n_trials=n_trials,
            train_ratio=train_ratio,
            random_seed=random_seed,
            cost_bps=cost_bps,
            horizon_months=horizon_months,
        )
        
        # JSONファイルに保存
        result_file = PROJECT_ROOT / f"optimization_result_{study_name}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ 結果を保存しました: {result_file}")
        print()
        print("【最良パラメータ】")
        for key, value in result_data["best_trial"]["params"].items():
            print(f"  {key}: {value:.6f}")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

