"""200 trial結果の評価スクリプト

200 trial完了後の成功条件をチェックし、候補群を選定します。
候補群は「上位＋分散」で選定し、多様性を確保します。

Usage:
    python evaluate_200trial_results.py --study-name optimization_timeseries_studyB_YYYYMMDD_HHMMSS
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import optuna
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))


def evaluate_200trial_success(
    study: optuna.Study,
) -> Dict[str, Any]:
    """
    200 trialの成功条件をチェック
    
    Args:
        study: Optunaのスタディ
    
    Returns:
        評価結果の辞書
    """
    completed_trials = [
        t for t in study.trials
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
    ]
    
    if not completed_trials:
        return {
            "status": "ERROR",
            "message": "完了したtrialがありません",
        }
    
    # Sharpe値の分布を計算
    sharpe_values = sorted([t.value for t in completed_trials], reverse=True)
    
    best_sharpe = sharpe_values[0]
    median_sharpe = sharpe_values[len(sharpe_values) // 2]
    
    # p95（上位5%）
    p95_idx = max(0, int(len(sharpe_values) * 0.05))
    p95_sharpe = sharpe_values[p95_idx] if p95_idx < len(sharpe_values) else sharpe_values[-1]
    
    # 上位10の最小値
    top10_sharpe = sharpe_values[:10]
    top10_min = min(top10_sharpe)
    
    print("Sharpe_excess分布:")
    print(f"  best: {best_sharpe:.4f}")
    print(f"  p95: {p95_sharpe:.4f}")
    print(f"  median: {median_sharpe:.4f}")
    print(f"  上位10の最小値: {top10_min:.4f}")
    print()
    
    # 成功条件（Study Bの場合）
    success_criteria = {
        "median > 0.10": median_sharpe > 0.10,
        "p95 > 0.25": p95_sharpe > 0.25,
        "上位10の最小値 > 0.15": top10_min > 0.15,
    }
    
    print("成功条件（Study B）:")
    for criterion, passed in success_criteria.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {criterion}: {passed}")
    print()
    
    # 上位10 trialを取得
    top10_trials = sorted(
        completed_trials,
        key=lambda t: t.value if t.value is not None else float('-inf'),
        reverse=True
    )[:10]
    
    # 上位10のパラメータの範囲をチェック
    key_params = ["bb_weight", "roe_min", "w_value", "w_forward_per"]
    param_ranges = {}
    param_extreme = {}
    
    for param_name in key_params:
        values = [t.params.get(param_name) for t in top10_trials if param_name in t.params]
        if values:
            param_ranges[param_name] = {
                "min": min(values),
                "max": max(values),
                "range": max(values) - min(values),
            }
            # 極端に端に張り付いていないかチェック（範囲の80%以上に集中していないか）
            # 実際には、探索範囲の端（0%または100%付近）に張り付いていないかを確認
            # 簡易版: 範囲が広い（分散がある）場合はOK
            param_extreme[param_name] = param_ranges[param_name]["range"] < 0.1  # 範囲が0.1未満なら張り付き
    
    print("上位10 trialのパラメータ範囲:")
    stability_check = True
    for param_name, range_info in param_ranges.items():
        extreme = param_extreme.get(param_name, False)
        status = "⚠️" if extreme else "✅"
        print(f"  {status} {param_name}: {range_info['min']:.4f} ～ {range_info['max']:.4f} (範囲: {range_info['range']:.4f})")
        if extreme:
            stability_check = False
    
    print()
    
    # 安定性チェック
    stability_criteria = {
        "パラメータが極端に端に張り付かない": stability_check,
    }
    
    print("安定性チェック:")
    for criterion, passed in stability_criteria.items():
        status = "✅" if passed else "⚠️"
        print(f"  {status} {criterion}: {passed}")
    print()
    
    # 危険シグナルのチェック
    danger_signals = []
    
    # 危険シグナル1: bestだけが異常に高く、p95や上位10が付いてこない
    if best_sharpe > 0.5 and (p95_sharpe < best_sharpe * 0.6 or top10_min < best_sharpe * 0.5):
        danger_signals.append(
            f"best（{best_sharpe:.4f}）だけが異常に高く、p95（{p95_sharpe:.4f}）や上位10最小（{top10_min:.4f}）が付いてこない"
        )
    
    # 危険シグナル2: bestが境界張り付きだらけ
    if not stability_check:
        danger_signals.append("パラメータが極端に端に張り付いている（範囲依存が強い可能性）")
    
    # 判定
    passed_count = sum(success_criteria.values())
    
    if passed_count == 3 and stability_check and not danger_signals:
        decision = "SUCCESS"
        recommendation = "成功条件を満たしています。Holdout検証に進むことを推奨します。"
    elif passed_count >= 2 and not danger_signals:
        decision = "CAUTION"
        recommendation = "大部分の条件を満たしていますが、一部が不足しています。慎重に判断してください。"
    elif danger_signals:
        decision = "WARNING"
        recommendation = f"危険シグナルが見つかりました。Holdout検証を実施する前に注意が必要です。\n  危険シグナル: {', '.join(danger_signals)}"
    else:
        decision = "FAIL"
        recommendation = "成功条件を満たしていません。範囲/目的関数/設計を見直すことを推奨します。"
    
    print("=" * 80)
    print(f"判定: {decision}")
    print("=" * 80)
    print(recommendation)
    if danger_signals:
        print()
        print("危険シグナル:")
        for signal in danger_signals:
            print(f"  ⚠️ {signal}")
    print()
    
    return {
        "status": decision,
        "n_completed": len(completed_trials),
        "best": best_sharpe,
        "p95": p95_sharpe,
        "median": median_sharpe,
        "top10_min": top10_min,
        "success_criteria": success_criteria,
        "stability_check": stability_check,
        "danger_signals": danger_signals,
        "recommendation": recommendation,
        "param_ranges": param_ranges,
        "top10_trials": [
            {"number": t.number, "value": t.value, "params": t.params}
            for t in top10_trials
        ],
    }


def select_diverse_candidates(
    study: optuna.Study,
    top_n: int = 20,
    select_k: int = 10,
    key_params: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    候補群を「上位＋分散」で選定（多様性を確保）
    
    Args:
        study: Optunaのスタディ
        top_n: 上位N trialから選定（デフォルト: 20）
        select_k: 選定する候補数（デフォルト: 10）
        key_params: 分散を考慮するパラメータ（デフォルト: bb_weight, roe_min, w_value, w_forward_per）
    
    Returns:
        選定された候補のリスト
    """
    if key_params is None:
        key_params = ["bb_weight", "roe_min", "w_value", "w_forward_per"]
    
    completed_trials = [
        t for t in study.trials
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
    ]
    
    if len(completed_trials) < top_n:
        top_n = len(completed_trials)
    
    # 上位N trialを取得
    top_trials = sorted(
        completed_trials,
        key=lambda t: t.value if t.value is not None else float('-inf'),
        reverse=True
    )[:top_n]
    
    # パラメータの値を抽出
    param_data = []
    trial_indices = []
    
    for i, trial in enumerate(top_trials):
        params = []
        valid = True
        for param_name in key_params:
            if param_name in trial.params:
                params.append(trial.params[param_name])
            else:
                valid = False
                break
        
        if valid:
            param_data.append(params)
            trial_indices.append(i)
    
    if not param_data:
        # パラメータが取得できない場合は、単純に上位Kを返す
        return [
            {
                "trial_number": t.number,
                "value": t.value,
                "params": t.params,
                "rank": i + 1,
            }
            for i, t in enumerate(top_trials[:select_k])
        ]
    
    param_array = np.array(param_data)
    
    # 標準化
    scaler = StandardScaler()
    param_scaled = scaler.fit_transform(param_array)
    
    # K-meansでクラスタリング（K=select_k）
    # ただし、データ数がselect_kより少ない場合は調整
    n_clusters = min(select_k, len(param_data))
    
    if n_clusters < 2:
        # クラスタリングできない場合は、単純に上位Kを返す
        return [
            {
                "trial_number": t.number,
                "value": t.value,
                "params": t.params,
                "rank": i + 1,
            }
            for i, t in enumerate(top_trials[:select_k])
        ]
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(param_scaled)
    
    # 各クラスタから最も良いtrialを1つずつ選ぶ
    selected_indices = set()
    selected_trials = []
    
    for cluster_id in range(n_clusters):
        cluster_mask = clusters == cluster_id
        cluster_local_indices = [trial_indices[i] for i in range(len(trial_indices)) if cluster_mask[i]]
        
        if cluster_local_indices:
            # クラスタ内で最も良いtrialを選ぶ
            best_in_cluster_idx = max(
                cluster_local_indices,
                key=lambda idx: top_trials[idx].value if top_trials[idx].value is not None else float('-inf')
            )
            
            if best_in_cluster_idx not in selected_indices:
                selected_indices.add(best_in_cluster_idx)
                trial = top_trials[best_in_cluster_idx]
                selected_trials.append({
                    "trial_number": trial.number,
                    "value": trial.value,
                    "params": trial.params,
                    "cluster": cluster_id,
                })
    
    # クラスタリングで選ばれなかった場合のフォールバック
    # 上位K trialの中で、まだ選ばれていないものを追加
    for trial in top_trials:
        if len(selected_trials) >= select_k:
            break
        if trial.number not in [s["trial_number"] for s in selected_trials]:
            # 元の順位を計算
            rank = next(
                (i + 1 for i, t in enumerate(top_trials) if t.number == trial.number),
                None
            )
            selected_trials.append({
                "trial_number": trial.number,
                "value": trial.value,
                "params": trial.params,
                "cluster": None,
                "rank": rank,
            })
    
    # 値でソート
    selected_trials.sort(key=lambda x: x["value"], reverse=True)
    
    return selected_trials[:select_k]


def main():
    parser = argparse.ArgumentParser(description="200 trial結果の評価と候補群選定")
    parser.add_argument("--study-name", type=str, required=True, help="スタディ名")
    parser.add_argument("--storage", type=str, help="Optunaストレージ（デフォルト: 自動推定）")
    parser.add_argument("--select-candidates", action="store_true", help="候補群を選定する")
    parser.add_argument("--top-n", type=int, default=20, help="上位N trialから選定（デフォルト: 20）")
    parser.add_argument("--select-k", type=int, default=10, help="選定する候補数（デフォルト: 10）")
    parser.add_argument("--output", type=str, help="候補群を保存するJSONファイルパス")
    
    args = parser.parse_args()
    
    # ストレージの設定
    if args.storage is None:
        args.storage = f"sqlite:///optuna_{args.study_name}.db"
    
    print("=" * 80)
    print(f"200 trial結果評価: {args.study_name}")
    print("=" * 80)
    print()
    
    # スタディを読み込み
    try:
        study = optuna.load_study(
            study_name=args.study_name,
            storage=args.storage,
        )
    except Exception as e:
        print(f"❌ スタディの読み込みに失敗しました: {e}")
        return 1
    
    # 成功条件の評価
    eval_result = evaluate_200trial_success(study)
    
    if eval_result.get("status") == "ERROR":
        print(f"❌ エラー: {eval_result.get('message')}")
        return 1
    
    # 候補群の選定
    if args.select_candidates:
        print("=" * 80)
        print("候補群の選定（上位＋分散）")
        print("=" * 80)
        print()
        
        candidates = select_diverse_candidates(
            study,
            top_n=args.top_n,
            select_k=args.select_k,
        )
        
        print(f"選定された候補（{len(candidates)}件）:")
        for i, candidate in enumerate(candidates, 1):
            cluster_info = f", cluster={candidate.get('cluster')}" if candidate.get('cluster') is not None else ""
            rank_info = f", rank={candidate.get('rank')}" if candidate.get('rank') is not None else ""
            print(f"  {i}. Trial #{candidate['trial_number']}: Sharpe={candidate['value']:.4f}{cluster_info}{rank_info}")
        
        print()
        
        # 候補群を保存
        if args.output:
            output_data = {
                "study_name": args.study_name,
                "selection_method": "diverse_candidates",
                "top_n": args.top_n,
                "select_k": args.select_k,
                "candidates": candidates,
                "evaluation": eval_result,
            }
            
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"候補群を {args.output} に保存しました")
            print()
        
        return 0 if eval_result.get("status") in ["SUCCESS", "CAUTION"] else 1
    else:
        # 評価のみ
        return 0 if eval_result.get("status") in ["SUCCESS", "CAUTION"] else 1


if __name__ == "__main__":
    sys.exit(main())

