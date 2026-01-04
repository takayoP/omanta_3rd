"""最終選定候補のパラメータとパフォーマンス指標をまとめたテーブルを作成"""

import json
from pathlib import Path
from typing import Dict, Any

# 対象のtrial_number
SELECTED_TRIALS = [96, 168, 180, 196]

# ファイルパス
CANDIDATES_FILE = "candidates_selected_2025_live.json"
HOLDOUT_2023_2024_FILE = "holdout_results_studyB_20251231_174014.json"
COST_SENSITIVITY_FILE = "holdout_cost_sensitivity/cost_sensitivity_analysis_20260101_183007.json"
HOLDOUT_2025_FILE = "holdout_2025_live_10bps.json"

def load_json(filepath: str) -> Dict[str, Any]:
    """JSONファイルを読み込む"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_params(candidates_data: Dict, trial_number: int) -> Dict[str, float]:
    """候補からパラメータを抽出"""
    for candidate in candidates_data['candidates']:
        if candidate['trial_number'] == trial_number:
            return candidate['params']
    return {}

def extract_holdout_2023_2024(holdout_data: Dict, trial_number: int) -> Dict[str, Any]:
    """2023-2024 Holdout結果を抽出"""
    for result in holdout_data['results']:
        if result['trial_number'] == trial_number:
            metrics = result['holdout_metrics']
            return {
                'sharpe_excess_0bps': metrics.get('sharpe_ratio', None),
                'sharpe_excess_2023': metrics.get('sharpe_excess_2023', None),
                'sharpe_excess_2024': metrics.get('sharpe_excess_2024', None),
                'cagr_excess_2023': metrics.get('cagr_excess_2023', None),
                'cagr_excess_2024': metrics.get('cagr_excess_2024', None),
                'max_drawdown': metrics.get('max_drawdown', None),
                'max_drawdown_diff': metrics.get('max_drawdown_diff', None),
                'turnover_annual': metrics.get('turnover_annual', None),
            }
    return {}

def extract_cost_sensitivity(cost_data: Dict, trial_number: int) -> Dict[str, Any]:
    """コスト感度分析結果を抽出"""
    trial_str = str(trial_number)
    if trial_str not in cost_data['candidate_rankings']:
        return {}
    
    ranking = cost_data['candidate_rankings'][trial_str]
    sharpe_by_cost = ranking.get('sharpe_by_cost', {})
    
    return {
        'sharpe_excess_10bps': sharpe_by_cost.get('10.0', None),
        'sharpe_excess_20bps': sharpe_by_cost.get('20.0', None),
        'sharpe_excess_30bps': sharpe_by_cost.get('30.0', None),
        'sharpe_after_cost_10bps': ranking.get('sharpe_after_cost_by_cost', {}).get('10.0', None),
        'sharpe_after_cost_20bps': ranking.get('sharpe_after_cost_by_cost', {}).get('20.0', None),
        'max_drawdown_10bps': ranking.get('maxdd_by_cost', {}).get('10.0', None),
        'max_drawdown_20bps': ranking.get('maxdd_by_cost', {}).get('20.0', None),
    }

def extract_holdout_2025(holdout_2025_data: Dict, trial_number: int) -> Dict[str, Any]:
    """2025疑似ライブ結果を抽出"""
    for result in holdout_2025_data['results']:
        if result['trial_number'] == trial_number:
            metrics = result['holdout_metrics']
            return {
                'sharpe_excess_2025_10bps': metrics.get('sharpe_ratio', None),
                'cagr_excess_2025_10bps': metrics.get('cagr', None),
                'max_drawdown_2025': metrics.get('max_drawdown', None),
                'sharpe_after_cost_2025': metrics.get('sharpe_excess_after_cost', None),
            }
    return {}

def main():
    """メイン処理"""
    print("データを読み込んでいます...")
    
    # データを読み込む
    candidates_data = load_json(CANDIDATES_FILE)
    holdout_2023_2024_data = load_json(HOLDOUT_2023_2024_FILE)
    cost_data = load_json(COST_SENSITIVITY_FILE)
    holdout_2025_data = load_json(HOLDOUT_2025_FILE)
    
    # 各候補のデータを統合
    final_candidates = {}
    
    for trial_number in SELECTED_TRIALS:
        trial_str = str(trial_number)
        final_candidates[trial_str] = {
            'trial_number': trial_number,
            'params': extract_params(candidates_data, trial_number),
            'holdout_2023_2024': extract_holdout_2023_2024(holdout_2023_2024_data, trial_number),
            'cost_sensitivity': extract_cost_sensitivity(cost_data, trial_number),
            'holdout_2025': extract_holdout_2025(holdout_2025_data, trial_number),
        }
    
    # JSONファイルに保存
    output_file = "final_selected_candidates.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_candidates, f, indent=2, ensure_ascii=False)
    
    print(f"データを {output_file} に保存しました。")
    
    # 簡易表示
    print("\n=== 主要指標の確認 ===")
    for trial_str in sorted(final_candidates.keys(), key=int):
        data = final_candidates[trial_str]
        print(f"\n#{data['trial_number']}:")
        print(f"  2023-2024 Holdout (0bps): Sharpe={data['holdout_2023_2024'].get('sharpe_excess_0bps', 'N/A'):.4f}")
        print(f"  2023-2024 Holdout (10bps): Sharpe={data['cost_sensitivity'].get('sharpe_excess_10bps', 'N/A'):.4f}")
        print(f"  2023-2024 Holdout (20bps): Sharpe={data['cost_sensitivity'].get('sharpe_excess_20bps', 'N/A'):.4f}")
        print(f"  2025 (10bps): Sharpe={data['holdout_2025'].get('sharpe_excess_2025_10bps', 'N/A'):.4f}")

if __name__ == "__main__":
    main()



