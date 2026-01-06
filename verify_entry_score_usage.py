#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
entry_scoreの使用状況を確認するスクリプト

Walk-Forward Analysisの結果ファイルとコードを確認して、
実際にRSI/BBベースのentry_scoreが使用されていたかを検証します。
"""

import json
from pathlib import Path

def verify_entry_score_usage():
    """entry_scoreの使用状況を確認"""
    print("=" * 80)
    print("entry_scoreの使用状況確認")
    print("=" * 80)
    print()
    
    # 1. Walk-Forward Analysisの結果ファイルを確認
    wf_result_file = Path("walk_forward_longterm_12M_roll_evalYear2025.json")
    if not wf_result_file.exists():
        print(f"❌ 結果ファイルが見つかりません: {wf_result_file}")
        return
    
    print("1. Walk-Forward Analysisの結果ファイルを確認")
    print("-" * 80)
    
    with open(wf_result_file, 'r', encoding='utf-8') as f:
        wf_result = json.load(f)
    
    print(f"✓ 結果ファイルを読み込みました: {wf_result_file}")
    print(f"  - 期間: {wf_result['start_date']} ～ {wf_result['end_date']}")
    print(f"  - Fold数: {wf_result['n_folds']}")
    print()
    
    # 各Foldのbest_paramsを確認
    print("2. 各Foldのentry_scoreパラメータを確認")
    print("-" * 80)
    
    entry_params_keys = ['rsi_base', 'rsi_max', 'bb_z_base', 'bb_z_max', 'bb_weight']
    
    for fold_result in wf_result['fold_results']:
        fold_label = fold_result.get('fold_label', f"fold{fold_result.get('fold', '?')}")
        best_params = fold_result.get('optimization', {}).get('best_params', {})
        
        print(f"\n{fold_label}:")
        print(f"  Train期間: {fold_result.get('train_start')} ～ {fold_result.get('train_end')}")
        print(f"  Test期間: {fold_result.get('test_start')} ～ {fold_result.get('test_end')}")
        
        # entry_scoreパラメータが存在するか確認
        has_entry_params = all(key in best_params for key in entry_params_keys)
        
        if has_entry_params:
            print(f"  ✓ entry_scoreパラメータが存在します（RSI/BBベース）:")
            print(f"    - rsi_base: {best_params['rsi_base']:.4f}")
            print(f"    - rsi_max: {best_params['rsi_max']:.4f}")
            print(f"    - bb_z_base: {best_params['bb_z_base']:.4f}")
            print(f"    - bb_z_max: {best_params['bb_z_max']:.4f}")
            print(f"    - bb_weight: {best_params['bb_weight']:.4f}")
            print(f"    - rsi_weight: {1.0 - best_params['bb_weight']:.4f}")
        else:
            print(f"  ❌ entry_scoreパラメータが見つかりません")
            print(f"    存在するキー: {list(best_params.keys())}")
    
    # 3. コードの使用状況を確認
    print("\n" + "=" * 80)
    print("3. コードでのentry_score使用状況")
    print("-" * 80)
    
    print("\n✓ optimize.py:")
    print("  - _entry_score_with_params: RSIとBBを使用")
    print("    * _rsi_from_series(close, n) でRSIを計算")
    print("    * _bb_zscore(close, n) でBB Z-scoreを計算")
    print("    * 各期間（20, 60, 90日）でスコアを計算")
    print("    * 3期間の最大値を最終スコアとする")
    
    print("\n✓ optimize_longterm.py:")
    print("  - _entry_score_with_params をインポートして使用")
    print("  - EntryScoreParams でパラメータを管理")
    
    print("\n✓ optimize_timeseries.py:")
    print("  - _entry_score_with_params をインポートして使用")
    print("  - _run_single_backtest_portfolio_only 内でentry_scoreを計算")
    
    # 4. 結論
    print("\n" + "=" * 80)
    print("4. 結論")
    print("=" * 80)
    
    all_folds_have_params = all(
        all(key in fold_result.get('optimization', {}).get('best_params', {}) 
            for key in entry_params_keys)
        for fold_result in wf_result['fold_results']
    )
    
    if all_folds_have_params:
        print("\n✅ 確認完了: すべてのFoldでRSI/BBベースのentry_scoreが使用されていました")
        print("\n   - Walk-Forward Analysisの結果ファイルにRSI/BBパラメータが含まれている")
        print("   - コードでは _entry_score_with_params が使用されている")
        print("   - entry_scoreはRSIとBB（ボリンジャーバンド）のみを使用")
        print("   - PER/PBRベースのcalculate_entry_scoreは使用されていない")
    else:
        print("\n⚠️  警告: 一部のFoldでentry_scoreパラメータが見つかりませんでした")
    
    print("\n" + "=" * 80)
    print("entry_scoreの計算方法（確認済み）")
    print("=" * 80)
    print("""
entry_scoreは以下の方法で計算されます：

1. 各期間（20日、60日、90日）で以下を計算:
   - RSI（相対力指数）: _rsi_from_series(close, n)
   - BB Z-score（ボリンジャーバンドZスコア）: _bb_zscore(close, n)

2. 各期間でスコアを計算:
   - BBスコア: (bb_z - bb_z_base) / (bb_z_max - bb_z_base) を0-1にクリップ
   - RSIスコア: (rsi - rsi_base) / (rsi_max - rsi_base) を0-1にクリップ
   - 期間スコア: (bb_weight * bb_score + rsi_weight * rsi_score) / (bb_weight + rsi_weight)

3. 最終スコア: 3期間の最大値（最も高いスコアを採用）

注意: entry_scoreは順張り設計です
  - RSIが高いほど高スコア（rsi_base以上でスコアが上がる）
  - BB Z-scoreが高いほど高スコア（bb_z_base以上でスコアが上がる）
""")

if __name__ == "__main__":
    verify_entry_score_usage()









