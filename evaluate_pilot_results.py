"""パイロット結果（50 trial）の評価スクリプト

50 trial時点での判断基準をチェックし、200 trialに進むかどうかを判定します。

Usage:
    python evaluate_pilot_results.py --study-name optimization_timeseries_studyA_YYYYMMDD_HHMMSS
"""

import argparse
import sys
from pathlib import Path
import optuna
import numpy as np
from typing import Dict, Any, List

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))


def evaluate_pilot_results(
    study_name: str,
    storage: str = None,
) -> Dict[str, Any]:
    """
    パイロット結果（50 trial）を評価
    
    Args:
        study_name: Optunaのスタディ名
        storage: Optunaストレージ（Noneの場合は自動推定）
    
    Returns:
        評価結果の辞書
    """
    if storage is None:
        storage = f"sqlite:///optuna_{study_name}.db"
    
    print("=" * 80)
    print(f"パイロット結果評価: {study_name}")
    print("=" * 80)
    print()
    
    # スタディを読み込み
    try:
        study = optuna.load_study(
            study_name=study_name,
            storage=storage,
        )
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"スタディの読み込みに失敗しました: {e}",
        }
    
    # 完了したtrialを取得
    completed_trials = [
        t for t in study.trials 
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
    ]
    
    if not completed_trials:
        return {
            "status": "ERROR",
            "message": "完了したtrialがありません",
        }
    
    print(f"完了したtrial数: {len(completed_trials)}")
    print()
    
    # Sharpe値の分布を計算
    sharpe_values = sorted([t.value for t in completed_trials], reverse=True)
    
    best_sharpe = sharpe_values[0]
    median_sharpe = sharpe_values[len(sharpe_values) // 2]
    
    # p95（上位5%）
    p95_idx = max(0, int(len(sharpe_values) * 0.05))
    p95_sharpe = sharpe_values[p95_idx] if p95_idx < len(sharpe_values) else sharpe_values[-1]
    
    mean_sharpe = np.mean(sharpe_values)
    std_sharpe = np.std(sharpe_values)
    
    print("Sharpe_excess分布:")
    print(f"  best: {best_sharpe:.4f}")
    print(f"  p95: {p95_sharpe:.4f}")
    print(f"  median: {median_sharpe:.4f}")
    print(f"  mean: {mean_sharpe:.4f}")
    print(f"  std: {std_sharpe:.4f}")
    print()
    
    # 判断基準
    criteria = {
        "median > -0.05": median_sharpe > -0.05,
        "p95 > 0": p95_sharpe > 0.0,
        "best > 0.15": best_sharpe > 0.15,
    }
    
    print("判断基準:")
    for criterion, passed in criteria.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {criterion}: {passed}")
    print()
    
    # 判定
    passed_count = sum(criteria.values())
    
    if passed_count == 3:
        decision = "GO"
        recommendation = "全ての基準を満たしています。200 trialに進むことを推奨します。"
    elif passed_count == 2:
        decision = "CAUTION"
        recommendation = "2/3の基準を満たしていますが、1つが不足しています。慎重に判断してください。"
    elif passed_count == 1:
        decision = "WARNING"
        recommendation = "1/3の基準しか満たしていません。200 trialに進む前に範囲/目的関数/設計を見直すことを推奨します。"
    else:
        decision = "NO_GO"
        recommendation = "基準を満たしていません。200 trialに進む前に範囲/目的関数/設計を見直す必要があります。"
    
    print("=" * 80)
    print(f"判定: {decision}")
    print("=" * 80)
    print(recommendation)
    print()
    
    # 上位5 trialのパラメータを表示
    top5_trials = sorted(
        completed_trials,
        key=lambda t: t.value if t.value is not None else float('-inf'),
        reverse=True
    )[:5]
    
    print("上位5 trialのSharpe値:")
    for i, trial in enumerate(top5_trials, 1):
        print(f"  #{trial.number}: {trial.value:.4f}")
    print()
    
    return {
        "status": decision,
        "study_name": study_name,
        "n_completed": len(completed_trials),
        "best": best_sharpe,
        "p95": p95_sharpe,
        "median": median_sharpe,
        "mean": mean_sharpe,
        "std": std_sharpe,
        "criteria": criteria,
        "recommendation": recommendation,
        "top5_trials": [
            {"number": t.number, "value": t.value, "params": t.params}
            for t in top5_trials
        ],
    }


def compare_studies(
    study_a_name: str,
    study_b_name: str,
    storage_a: str = None,
    storage_b: str = None,
) -> Dict[str, Any]:
    """
    Study AとBを比較
    
    Args:
        study_a_name: Study Aのスタディ名
        study_b_name: Study Bのスタディ名
        storage_a: Study Aのストレージ
        storage_b: Study Bのストレージ
    
    Returns:
        比較結果の辞書
    """
    print("=" * 80)
    print("Study A/B 比較")
    print("=" * 80)
    print()
    
    result_a = evaluate_pilot_results(study_a_name, storage_a)
    print()
    
    result_b = evaluate_pilot_results(study_b_name, storage_b)
    print()
    
    print("=" * 80)
    print("比較結果")
    print("=" * 80)
    print()
    
    if result_a.get("status") == "ERROR" or result_b.get("status") == "ERROR":
        return {
            "status": "ERROR",
            "study_a": result_a,
            "study_b": result_b,
        }
    
    print("Study A:")
    print(f"  best: {result_a['best']:.4f}")
    print(f"  median: {result_a['median']:.4f}")
    print(f"  判定: {result_a['status']}")
    print()
    
    print("Study B:")
    print(f"  best: {result_b['best']:.4f}")
    print(f"  median: {result_b['median']:.4f}")
    print(f"  判定: {result_b['status']}")
    print()
    
    # どちらが良いか判定
    best_a = result_a["best"]
    best_b = result_b["best"]
    median_a = result_a["median"]
    median_b = result_b["median"]
    
    diff_best = best_a - best_b
    diff_median = median_a - median_b
    
    if abs(diff_best) < 0.05 and abs(diff_median) < 0.05:
        comparison = "両方そこそこ（どちらも似たような結果）"
        recommendation = "両方のStudyを200 trialに進めることを推奨します。"
    elif best_a > best_b + 0.1 and median_a > median_b + 0.05:
        comparison = "Study Aの方が明確に良い"
        recommendation = "Study Aに集中して200 trialに進むことを推奨します。"
    elif best_b > best_a + 0.1 and median_b > median_a + 0.05:
        comparison = "Study Bの方が明確に良い"
        recommendation = "Study Bに集中して200 trialに進むことを推奨します。"
    else:
        comparison = "優劣が明確でない"
        recommendation = "両方のStudyを200 trialに進めるか、慎重に判断してください。"
    
    print(f"比較: {comparison}")
    print(f"  bestの差: {diff_best:.4f} (A - B)")
    print(f"  medianの差: {diff_median:.4f} (A - B)")
    print()
    print(f"推奨: {recommendation}")
    print()
    
    return {
        "status": "OK",
        "study_a": result_a,
        "study_b": result_b,
        "comparison": comparison,
        "recommendation": recommendation,
        "diff_best": diff_best,
        "diff_median": diff_median,
    }


def main():
    parser = argparse.ArgumentParser(description="パイロット結果（50 trial）の評価")
    parser.add_argument("--study-name", type=str, help="スタディ名（単一評価の場合）")
    parser.add_argument("--study-a", type=str, help="Study Aのスタディ名（比較の場合）")
    parser.add_argument("--study-b", type=str, help="Study Bのスタディ名（比較の場合）")
    parser.add_argument("--storage", type=str, help="Optunaストレージ（デフォルト: 自動推定）")
    parser.add_argument("--storage-a", type=str, help="Study Aのストレージ")
    parser.add_argument("--storage-b", type=str, help="Study Bのストレージ")
    
    args = parser.parse_args()
    
    if args.study_a and args.study_b:
        # 比較モード
        result = compare_studies(
            args.study_a,
            args.study_b,
            args.storage_a or args.storage,
            args.storage_b or args.storage,
        )
        
        if result.get("status") == "ERROR":
            print("❌ エラーが発生しました")
            return 1
        
        # 判定に応じて終了コードを設定
        status_a = result["study_a"].get("status")
        status_b = result["study_b"].get("status")
        
        if status_a in ["NO_GO", "WARNING"] and status_b in ["NO_GO", "WARNING"]:
            return 1
        elif status_a == "NO_GO" or status_b == "NO_GO":
            return 1
        
        return 0
    elif args.study_name:
        # 単一評価モード
        result = evaluate_pilot_results(args.study_name, args.storage)
        
        if result.get("status") == "ERROR":
            print("❌ エラーが発生しました")
            return 1
        elif result.get("status") == "NO_GO":
            return 1
        
        return 0
    else:
        print("❌ --study-name または --study-a/--study-b を指定してください")
        return 1


if __name__ == "__main__":
    sys.exit(main())



















