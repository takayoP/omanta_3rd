"""
最適化の進行状況を確認するスクリプト
"""

from __future__ import annotations

import sys
from pathlib import Path
import optuna


def check_progress(study_name: str):
    """最適化の進行状況を確認"""
    storage = f"sqlite:///optuna_{study_name}.db"
    db_path = Path(f"optuna_{study_name}.db")
    
    if not db_path.exists():
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        print("   最適化がまだ開始されていない可能性があります。")
        return
    
    print("=" * 80)
    print("最適化の進行状況")
    print("=" * 80)
    print(f"スタディ名: {study_name}")
    print(f"データベースファイル: {db_path}")
    print(f"ファイルサイズ: {db_path.stat().st_size / 1024:.2f} KB")
    print()
    
    try:
        study = optuna.load_study(study_name=study_name, storage=storage)
        
        # 全トライアル数
        all_trials = study.trials
        completed_trials = [t for t in all_trials if t.state == optuna.trial.TrialState.COMPLETE]
        running_trials = [t for t in all_trials if t.state == optuna.trial.TrialState.RUNNING]
        failed_trials = [t for t in all_trials if t.state == optuna.trial.TrialState.FAIL]
        waiting_trials = [t for t in all_trials if t.state == optuna.trial.TrialState.WAITING]
        
        print(f"【トライアル状況】")
        print(f"  完了: {len(completed_trials)}")
        print(f"  実行中: {len(running_trials)}")
        print(f"  待機中: {len(waiting_trials)}")
        print(f"  失敗: {len(failed_trials)}")
        print(f"  合計: {len(all_trials)}")
        print()
        
        if completed_trials:
            # 完了したトライアルの結果
            values = [t.value for t in completed_trials if t.value is not None]
            
            if values:
                import numpy as np
                print(f"【完了トライアルの結果】")
                print(f"  最良値: {max(values):.4f}")
                print(f"  最悪値: {min(values):.4f}")
                print(f"  平均値: {np.mean(values):.4f}")
                print(f"  中央値: {np.median(values):.4f}")
                print()
                
                # 最良トライアル
                best_trial = study.best_trial
                print(f"【最良トライアル】")
                print(f"  トライアル番号: {best_trial.number}")
                print(f"  値: {best_trial.value:.4f}")
                print()
                
                # 最新の完了トライアル（上位5件）
                sorted_completed = sorted(
                    [t for t in completed_trials if t.value is not None],
                    key=lambda t: t.value,
                    reverse=True
                )
                print(f"【上位5トライアル】")
                for i, trial in enumerate(sorted_completed[:5], 1):
                    print(f"  {i}. Trial {trial.number}: {trial.value:.4f}")
                print()
        
        if running_trials:
            print(f"【実行中のトライアル】")
            for trial in running_trials:
                print(f"  Trial {trial.number}: 実行中...")
            print()
        
        if failed_trials:
            print(f"【失敗したトライアル】")
            for trial in failed_trials[:5]:  # 最大5件表示
                print(f"  Trial {trial.number}: {trial.system_attrs.get('fail_reason', 'Unknown error')}")
            if len(failed_trials) > 5:
                print(f"  ... 他 {len(failed_trials) - 5}件")
            print()
        
        # 進捗率
        if len(all_trials) > 0:
            progress = len(completed_trials) / len(all_trials) * 100
            print(f"【進捗】")
            print(f"  {len(completed_trials)}/{len(all_trials)} ({progress:.1f}%)")
            print()
        
    except Exception as e:
        print(f"❌ スタディの読み込みに失敗しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    study_name = "optimization_timeseries_20251230_phase1"
    check_progress(study_name)







