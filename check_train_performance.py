#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
train期間の超過リターンが低い問題の確認スクリプト

確認項目：
1. trainでn_used_datesとmax_eval_end_usedを確認
2. Optunaの方向とbest_valueの整合性確認
3. 旧best paramsを今の等ウェイト実装で再評価
"""

import json
import optuna
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta

# 最適化結果JSONを読み込む
result_file_20260112 = Path("optimization_result_operational_24M_lambda0.00_20260112.json")
result_file_20260111 = Path("optimization_result_operational_24M_lambda0.00_20260111.json")

print("=" * 80)
print("train期間の超過リターンが低い問題の確認")
print("=" * 80)
print()

# 現在の結果（2026-01-12）
if result_file_20260112.exists():
    with open(result_file_20260112, "r", encoding="utf-8") as f:
        data_current = json.load(f)
    
    print("【現在の結果（2026-01-12）】")
    print(f"  train_dates_first: {data_current.get('train_dates_first')}")
    print(f"  train_dates_last: {data_current.get('train_dates_last')}")
    print(f"  num_train_periods: {data_current.get('num_train_periods')}")
    print(f"  train_performance.mean_annual_excess_return_pct: {data_current.get('train_performance', {}).get('mean_annual_excess_return_pct', 'N/A')}%")
    print(f"  best_trial.value: {data_current.get('best_trial', {}).get('value', 'N/A')}")
    print()
    
    # Optuna studyを読み込む
    study_name = data_current.get('study_name', '')
    storage_path = f"sqlite:///optuna_{study_name}.db"
    
    if Path(f"optuna_{study_name}.db").exists():
        try:
            study = optuna.load_study(study_name=study_name, storage=storage_path)
            
            print("  【Optuna study情報】")
            print(f"    direction: {study.direction}")
            print(f"    best_value: {study.best_value}")
            print(f"    best_trial.number: {study.best_trial.number}")
            print()
            
            # 上位trialのvalueを取得
            completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
            if completed_trials:
                # direction="maximize"の場合は、valueが大きい順にソート
                sorted_trials = sorted(completed_trials, key=lambda t: t.value, reverse=True)
                print("  【上位trialのvalue（トップ5、valueが大きい順）】")
                for i, trial in enumerate(sorted_trials[:5], 1):
                    print(f"    {i}. Trial {trial.number}: value={trial.value:.4f}%")
                print("  【下位trialのvalue（ワースト5、valueが小さい順）】")
                for i, trial in enumerate(sorted_trials[-5:], 1):
                    print(f"    {i}. Trial {trial.number}: value={trial.value:.4f}%")
                print()
        except Exception as e:
            print(f"  ⚠️  Optuna studyの読み込みに失敗: {e}")
            print()
else:
    print("⚠️  現在の結果ファイルが見つかりません")
    print()

# 以前の結果（2026-01-11）
if result_file_20260111.exists():
    with open(result_file_20260111, "r", encoding="utf-8") as f:
        data_previous = json.load(f)
    
    print("【以前の結果（2026-01-11）】")
    print(f"  train_dates_first: {data_previous.get('train_dates_first')}")
    print(f"  train_dates_last: {data_previous.get('train_dates_last')}")
    print(f"  num_train_periods: {data_previous.get('num_train_periods')}")
    print(f"  train_performance.mean_annual_excess_return_pct: {data_previous.get('train_performance', {}).get('mean_annual_excess_return_pct', 'N/A')}%")
    print(f"  best_trial.value: {data_previous.get('best_trial', {}).get('value', 'N/A')}")
    print()
    
    # Optuna studyを読み込む
    study_name_prev = data_previous.get('study_name', '')
    storage_path_prev = f"sqlite:///optuna_{study_name_prev}.db"
    
    if Path(f"optuna_{study_name_prev}.db").exists():
        try:
            study_prev = optuna.load_study(study_name=study_name_prev, storage=storage_path_prev)
            
            print("  【Optuna study情報】")
            print(f"    direction: {study_prev.direction}")
            print(f"    best_value: {study_prev.best_value}")
            print(f"    best_trial.number: {study_prev.best_trial.number}")
            print()
            
            # 上位trialのvalueを取得
            completed_trials_prev = [t for t in study_prev.trials if t.state == optuna.trial.TrialState.COMPLETE]
            if completed_trials_prev:
                # direction="maximize"の場合は、valueが大きい順にソート
                sorted_trials_prev = sorted(completed_trials_prev, key=lambda t: t.value, reverse=True)
                print("  【上位trialのvalue（トップ5、valueが大きい順）】")
                for i, trial in enumerate(sorted_trials_prev[:5], 1):
                    print(f"    {i}. Trial {trial.number}: value={trial.value:.4f}%")
                print("  【下位trialのvalue（ワースト5、valueが小さい順）】")
                for i, trial in enumerate(sorted_trials_prev[-5:], 1):
                    print(f"    {i}. Trial {trial.number}: value={trial.value:.4f}%")
                print()
        except Exception as e:
            print(f"  ⚠️  Optuna studyの読み込みに失敗: {e}")
            print()
else:
    print("⚠️  以前の結果ファイルが見つかりません")
    print()

print("=" * 80)
print("確認項目")
print("=" * 80)
print()
print("1. trainでn_used_datesとmax_eval_end_usedを確認")
print("   → 実際のログファイルまたは最適化実行時の出力を確認してください")
print()
print("2. Optunaの方向とbest_valueの整合性確認")
print("   → 上記の出力を確認してください")
print()
print("3. 旧best paramsを今の等ウェイト実装で再評価")
print("   → 別途スクリプトで実行する必要があります")
print()

