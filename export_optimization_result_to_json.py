"""
既存のOptuna最適化結果をJSONファイルにエクスポートするスクリプト

Usage:
    python export_optimization_result_to_json.py --study-name optimization_longterm_studyC_20260102_205614
"""

import argparse
import json
import optuna
from pathlib import Path


def export_study_to_json(study_name: str, storage: str = None) -> None:
    """
    OptunaのスタディをJSONファイルにエクスポート
    
    Args:
        study_name: スタディ名
        storage: ストレージパス（Noneの場合は自動検出）
    """
    # ストレージの設定
    if storage is None:
        # デフォルトのSQLiteファイルを検索
        db_file = f"optuna_{study_name}.db"
        if not Path(db_file).exists():
            raise FileNotFoundError(f"データベースファイルが見つかりません: {db_file}")
        storage = f"sqlite:///{db_file}"
    
    # スタディを読み込み
    study = optuna.load_study(study_name=study_name, storage=storage)
    
    # 最良試行の情報を取得
    best_trial = study.best_trial
    
    # 正規化パラメータを計算（重みの合計が1になるように）
    best_params = best_trial.params.copy()
    w_quality = best_params.get("w_quality", 0.0)
    w_value = best_params.get("w_value", 0.0)
    w_growth = best_params.get("w_growth", 0.0)
    w_record_high = best_params.get("w_record_high", 0.0)
    w_size = best_params.get("w_size", 0.0)
    
    total = w_quality + w_value + w_growth + w_record_high + w_size
    if total > 0:
        w_quality_norm = w_quality / total
        w_value_norm = w_value / total
        w_growth_norm = w_growth / total
        w_record_high_norm = w_record_high / total
        w_size_norm = w_size / total
    else:
        w_quality_norm = w_quality
        w_value_norm = w_value
        w_growth_norm = w_growth
        w_record_high_norm = w_record_high
        w_size_norm = w_size
    
    # JSONデータを構築
    result_data = {
        "study_name": study_name,
        "best_trial": {
            "number": best_trial.number,
            "value": study.best_value,
            "params": best_params,
        },
        "normalized_params": {
            "w_quality": w_quality_norm,
            "w_value": w_value_norm,
            "w_growth": w_growth_norm,
            "w_record_high": w_record_high_norm,
            "w_size": w_size_norm,
            "w_forward_per": best_params.get("w_forward_per", 0.0),
            "w_pbr": 1.0 - best_params.get("w_forward_per", 0.0),
            "roe_min": best_params.get("roe_min", 0.0),
            "liquidity_quantile_cut": best_params.get("liquidity_quantile_cut", 0.0),
            "rsi_base": best_params.get("rsi_base", 0.0),
            "rsi_max": best_params.get("rsi_max", 0.0),
            "bb_z_base": best_params.get("bb_z_base", 0.0),
            "bb_z_max": best_params.get("bb_z_max", 0.0),
            "bb_weight": best_params.get("bb_weight", 0.0),
            "rsi_weight": 1.0 - best_params.get("bb_weight", 0.0),
        },
        "n_trials": len(study.trials),
        "description": "長期保有型パラメータ最適化結果",
    }
    
    # JSONファイルに保存
    result_file = f"optimization_result_{study_name}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)
    
    print(f"最適化結果を保存しました: {result_file}")
    print(f"  最良試行: {best_trial.number}")
    print(f"  最良値: {study.best_value:.4f}%")
    print(f"  試行回数: {len(study.trials)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="既存のOptuna最適化結果をJSONファイルにエクスポート"
    )
    parser.add_argument(
        "--study-name",
        type=str,
        required=True,
        help="スタディ名（例: optimization_longterm_studyC_20260102_205614）",
    )
    parser.add_argument(
        "--storage",
        type=str,
        default=None,
        help="ストレージパス（Noneの場合は自動検出）",
    )
    
    args = parser.parse_args()
    
    export_study_to_json(args.study_name, args.storage)











