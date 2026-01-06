"""
最適化結果の分析スクリプト

Step 1の評価指標を計算:
- best/p95/medianのSharpe_excess
- 上位5 trialのパラメータ分布（極端にブレるか）
- missing_countが上位に偏ってないか（欠損が都合よく効いていないか）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd
import optuna
from collections import Counter


def load_study(study_name: str) -> optuna.Study:
    """Optunaスタディを読み込む"""
    storage = f"sqlite:///optuna_{study_name}.db"
    study = optuna.load_study(study_name=study_name, storage=storage)
    return study


def analyze_sharpe_distribution(study: optuna.Study) -> Dict[str, float]:
    """Sharpe_excessの分布を分析"""
    completed_trials = [
        t for t in study.trials 
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
    ]
    
    if not completed_trials:
        return {
            "best": None,
            "p95": None,
            "median": None,
            "p5": None,
            "mean": None,
            "std": None,
            "count": 0,
        }
    
    values = [t.value for t in completed_trials]
    values_array = np.array(values)
    
    return {
        "best": float(np.max(values_array)),
        "p95": float(np.percentile(values_array, 95)),
        "median": float(np.median(values_array)),
        "p5": float(np.percentile(values_array, 5)),
        "mean": float(np.mean(values_array)),
        "std": float(np.std(values_array, ddof=1)),
        "count": len(values),
    }


def analyze_top5_parameters(study: optuna.Study) -> Dict[str, Any]:
    """上位5 trialのパラメータ分布を分析"""
    completed_trials = [
        t for t in study.trials 
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
    ]
    
    if not completed_trials:
        return {"error": "完了したトライアルがありません"}
    
    # 上位5 trialを取得
    sorted_trials = sorted(completed_trials, key=lambda t: t.value, reverse=True)
    top5_trials = sorted_trials[:5]
    
    # 各パラメータの分布を分析
    param_stats = {}
    
    # 全パラメータ名を取得
    all_params = set()
    for trial in top5_trials:
        all_params.update(trial.params.keys())
    
    for param_name in all_params:
        values = [t.params.get(param_name) for t in top5_trials if param_name in t.params]
        
        if not values:
            continue
        
        # 数値パラメータの場合
        if all(isinstance(v, (int, float)) for v in values):
            values_array = np.array(values)
            param_stats[param_name] = {
                "values": values.tolist(),
                "min": float(np.min(values_array)),
                "max": float(np.max(values_array)),
                "mean": float(np.mean(values_array)),
                "std": float(np.std(values_array, ddof=1)),
                "range_ratio": float(np.max(values_array) / np.min(values_array)) if np.min(values_array) > 0 else None,
            }
        else:
            # 非数値パラメータの場合
            param_stats[param_name] = {
                "values": values,
                "unique_count": len(set(values)),
            }
    
    return {
        "top5_trials": [
            {
                "trial_number": t.number,
                "value": t.value,
                "params": t.params,
            }
            for t in top5_trials
        ],
        "param_stats": param_stats,
    }


def check_missing_count_bias(study: optuna.Study) -> Dict[str, Any]:
    """missing_countが上位に偏ってないか確認"""
    completed_trials = [
        t for t in study.trials 
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
    ]
    
    if not completed_trials:
        return {"error": "完了したトライアルがありません"}
    
    # 上位10 trialと下位10 trialのmissing_countを比較
    sorted_trials = sorted(completed_trials, key=lambda t: t.value, reverse=True)
    top10_trials = sorted_trials[:10]
    bottom10_trials = sorted_trials[-10:] if len(sorted_trials) >= 10 else sorted_trials
    
    # 注意: 現在の実装ではmissing_countはtrialのuser_attrsに保存されていない可能性がある
    # ログから抽出するか、最適化スクリプトを修正して保存する必要がある
    
    # 暫定的に、パラメータから推測できないため、この分析はスキップ
    # 代わりに、最適化実行時のログを確認する必要がある
    
    return {
        "note": "missing_countの分析には、最適化実行時のログまたはuser_attrsへの保存が必要です",
        "top10_trials": [t.number for t in top10_trials],
        "bottom10_trials": [t.number for t in bottom10_trials],
    }


def evaluate_results(stats: Dict[str, float]) -> Dict[str, str]:
    """結果を評価（合格ラインの判定）"""
    best = stats.get("best")
    p95 = stats.get("p95")
    median = stats.get("median")
    
    if best is None or p95 is None or median is None:
        return {"status": "ERROR", "message": "統計値が不足しています"}
    
    # 合格ラインの判定
    # bestが0.44付近でも、p95が0.30前後、medianが0.10-0.20なら「普通にあり得る上振れ」
    # bestだけ0.44で、他が0近辺なら「当たりの可能性が高い」
    
    evaluations = []
    
    # 1. bestとp95の関係
    if p95 >= best * 0.68:  # p95がbestの68%以上（約0.30/0.44）
        evaluations.append("✅ p95がbestの68%以上: 再現性良好")
    elif p95 >= best * 0.50:
        evaluations.append("⚠️ p95がbestの50-68%: やや上振れの可能性")
    else:
        evaluations.append("❌ p95がbestの50%未満: 当たりの可能性が高い")
    
    # 2. bestとmedianの関係
    if median >= best * 0.23 and median <= best * 0.45:  # medianが0.10-0.20の範囲（best=0.44の場合）
        evaluations.append("✅ medianが適切な範囲: 普通にあり得る上振れ")
    elif median >= best * 0.10:
        evaluations.append("⚠️ medianがやや低い: 上振れの可能性")
    else:
        evaluations.append("❌ medianが非常に低い: 当たりの可能性が高い")
    
    # 3. 総合評価
    if p95 >= best * 0.68 and median >= best * 0.23:
        overall = "✅ 良好: 普通にあり得る上振れ"
    elif p95 >= best * 0.50 and median >= best * 0.10:
        overall = "⚠️ 注意: やや上振れの可能性"
    else:
        overall = "❌ 問題: 当たりの可能性が高い"
    
    return {
        "status": "OK",
        "evaluations": evaluations,
        "overall": overall,
    }


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description="最適化結果の分析")
    parser.add_argument(
        "--study-name",
        type=str,
        required=True,
        help="Optunaスタディ名（例: optimization_timeseries_20251230_phase1）",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="出力JSONファイルパス（指定しない場合は標準出力）",
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("最適化結果の分析")
    print("=" * 80)
    print(f"スタディ名: {args.study_name}")
    print()
    
    # スタディを読み込む
    try:
        study = load_study(args.study_name)
    except Exception as e:
        print(f"❌ スタディの読み込みに失敗しました: {e}")
        sys.exit(1)
    
    # 1. Sharpe_excessの分布を分析
    print("【1. Sharpe_excessの分布】")
    print("-" * 80)
    sharpe_stats = analyze_sharpe_distribution(study)
    
    if sharpe_stats["count"] == 0:
        print("❌ 完了したトライアルがありません")
        sys.exit(1)
    
    print(f"完了トライアル数: {sharpe_stats['count']}")
    print(f"best Sharpe_excess: {sharpe_stats['best']:.4f}")
    print(f"p95 Sharpe_excess: {sharpe_stats['p95']:.4f}")
    print(f"median Sharpe_excess: {sharpe_stats['median']:.4f}")
    print(f"p5 Sharpe_excess: {sharpe_stats['p5']:.4f}")
    print(f"mean Sharpe_excess: {sharpe_stats['mean']:.4f}")
    print(f"std Sharpe_excess: {sharpe_stats['std']:.4f}")
    print()
    
    # 評価
    evaluation = evaluate_results(sharpe_stats)
    print("【評価】")
    for eval_msg in evaluation.get("evaluations", []):
        print(f"  {eval_msg}")
    print(f"  総合: {evaluation.get('overall', 'N/A')}")
    print()
    
    # 2. 上位5 trialのパラメータ分布を分析
    print("【2. 上位5 trialのパラメータ分布】")
    print("-" * 80)
    param_analysis = analyze_top5_parameters(study)
    
    if "error" in param_analysis:
        print(f"❌ {param_analysis['error']}")
    else:
        print("上位5 trial:")
        for i, trial_info in enumerate(param_analysis["top5_trials"], 1):
            print(f"  {i}. Trial {trial_info['trial_number']}: Sharpe_excess = {trial_info['value']:.4f}")
        
        print()
        print("パラメータ統計（上位5 trial）:")
        for param_name, stats in param_analysis["param_stats"].items():
            if "range_ratio" in stats and stats["range_ratio"] is not None:
                range_ratio = stats["range_ratio"]
                if range_ratio > 2.0:
                    status = "❌ 極端にブレ"
                elif range_ratio > 1.5:
                    status = "⚠️ ややブレ"
                else:
                    status = "✅ 安定"
                
                print(f"  {param_name}:")
                print(f"    値: {stats['values']}")
                print(f"    範囲比: {range_ratio:.2f} ({status})")
                print(f"    平均: {stats['mean']:.4f}, 標準偏差: {stats['std']:.4f}")
            else:
                print(f"  {param_name}: {stats['values']}")
        print()
    
    # 3. missing_countの分析
    print("【3. missing_countの分析】")
    print("-" * 80)
    missing_analysis = check_missing_count_bias(study)
    
    if "error" in missing_analysis:
        print(f"❌ {missing_analysis['error']}")
    else:
        print(f"注意: {missing_analysis['note']}")
        print(f"上位10 trial: {missing_analysis['top10_trials']}")
        print(f"下位10 trial: {missing_analysis['bottom10_trials']}")
        print()
        print("※ missing_countの分析には、最適化実行時のログを確認するか、")
        print("  最適化スクリプトを修正してuser_attrsに保存する必要があります。")
        print()
    
    # 結果をJSONに保存
    result = {
        "study_name": args.study_name,
        "sharpe_stats": sharpe_stats,
        "evaluation": evaluation,
        "param_analysis": param_analysis,
        "missing_analysis": missing_analysis,
    }
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"結果を {args.output} に保存しました")
    else:
        print("=" * 80)
        print("結果（JSON形式）:")
        print("=" * 80)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()















