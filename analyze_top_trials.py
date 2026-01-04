"""上位10 trialの分析スクリプト

Optunaのstudyデータベースから上位10 trialのパラメータとobjective値を取得し、
クラスタリングやパラメータ分布を分析します。
"""

import json
import sys
from pathlib import Path
import optuna
import pandas as pd
import numpy as np

def analyze_top_trials(study_name: str, top_n: int = 10):
    """上位N trialを分析"""
    
    # Optunaスタディを読み込み
    storage = f"sqlite:///optuna_{study_name}.db"
    study = optuna.load_study(study_name=study_name, storage=storage)
    
    # 完了したtrialを取得
    completed_trials = [
        t for t in study.trials 
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
    ]
    
    if not completed_trials:
        print("完了したtrialが見つかりません")
        return
    
    # objective値でソート（降順）
    sorted_trials = sorted(
        completed_trials,
        key=lambda t: t.value if t.value is not None else float('-inf'),
        reverse=True
    )
    
    top_trials = sorted_trials[:top_n]
    
    print("=" * 80)
    print(f"上位{top_n} trialの分析")
    print("=" * 80)
    print()
    
    # 各trialの情報を収集
    results = []
    for i, trial in enumerate(top_trials, 1):
        result = {
            "rank": i,
            "trial_number": trial.number,
            "objective": trial.value,
            **trial.params
        }
        results.append(result)
    
    df = pd.DataFrame(results)
    
    # 統計情報を表示
    print(f"Objective値の分布:")
    print(f"  最良: {df['objective'].max():.4f}")
    print(f"  平均: {df['objective'].mean():.4f}")
    print(f"  中央値: {df['objective'].median():.4f}")
    print(f"  最小: {df['objective'].min():.4f}")
    print(f"  標準偏差: {df['objective'].std():.4f}")
    print()
    
    # 各パラメータの統計を表示
    param_cols = [col for col in df.columns if col not in ['rank', 'trial_number', 'objective']]
    
    print("パラメータの統計（上位10 trial）:")
    print("-" * 80)
    
    param_stats = []
    for param in param_cols:
        values = df[param].values
        param_stats.append({
            "parameter": param,
            "min": np.min(values),
            "max": np.max(values),
            "mean": np.mean(values),
            "median": np.median(values),
            "std": np.std(values),
            "range": np.max(values) - np.min(values),
        })
    
    param_stats_df = pd.DataFrame(param_stats).sort_values('range', ascending=False)
    
    for _, row in param_stats_df.iterrows():
        print(f"{row['parameter']:25s}: "
              f"min={row['min']:8.4f}, "
              f"max={row['max']:8.4f}, "
              f"mean={row['mean']:8.4f}, "
              f"range={row['range']:8.4f}")
    
    print()
    
    # core重みの合計を確認
    core_weight_params = ['w_quality', 'w_value', 'w_growth', 'w_record_high', 'w_size']
    if all(p in param_cols for p in core_weight_params):
        print("Core重みの合計（raw）:")
        df['core_weight_sum'] = df[core_weight_params].sum(axis=1)
        print(f"  平均: {df['core_weight_sum'].mean():.4f}")
        print(f"  最小: {df['core_weight_sum'].min():.4f}")
        print(f"  最大: {df['core_weight_sum'].max():.4f}")
        print(f"  標準偏差: {df['core_weight_sum'].std():.4f}")
        print()
    
    # JSONファイルに保存
    output_data = {
        "study_name": study_name,
        "top_n": top_n,
        "trials": []
    }
    
    for trial in top_trials:
        trial_data = {
            "trial_number": trial.number,
            "objective": trial.value,
            "params": trial.params.copy(),
        }
        
        # core重みの正規化後の値も計算
        if all(p in trial.params for p in core_weight_params):
            raw_weights = [trial.params[p] for p in core_weight_params]
            total = sum(raw_weights)
            if total > 0:
                normalized_weights = {p: trial.params[p] / total for p in core_weight_params}
                trial_data["params_normalized"] = normalized_weights
                trial_data["core_weight_sum_raw"] = total
        
        output_data["trials"].append(trial_data)
    
    output_file = f"top_{top_n}_trials_{study_name}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"結果を {output_file} に保存しました")
    
    # CSVにも保存（可視化用）
    csv_file = f"top_{top_n}_trials_{study_name}.csv"
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")
    print(f"CSV形式で {csv_file} にも保存しました")
    
    # パラメータ間の相関を分析（上位trialでの相関）
    print()
    print("パラメータ間の相関（上位10 trial、objective値との相関）:")
    print("-" * 80)
    
    correlations = []
    for param in param_cols:
        if param in df.columns:
            corr = df[param].corr(df['objective'])
            correlations.append({
                "parameter": param,
                "correlation_with_objective": corr
            })
    
    corr_df = pd.DataFrame(correlations).sort_values('correlation_with_objective', key=abs, ascending=False)
    for _, row in corr_df.iterrows():
        print(f"{row['parameter']:25s}: {row['correlation_with_objective']:7.4f}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python analyze_top_trials.py <study_name> [top_n]")
        print("例: python analyze_top_trials.py optimization_timeseries_20251230_194502 10")
        sys.exit(1)
    
    study_name = sys.argv[1]
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    analyze_top_trials(study_name, top_n)







