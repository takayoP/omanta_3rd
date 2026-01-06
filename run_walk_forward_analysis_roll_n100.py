#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Walk-Forward Analysis実行スクリプト（roll方式、n_trials=100）
長期保有型のWalk-Forward検証をroll方式で実行します（試行回数100）
"""

import subprocess
import sys
from datetime import datetime

# パラメータ設定
START_DATE = "2020-01-01"
END_DATE = "2025-12-31"
HORIZON = 12  # ホライズン（月数: 12, 24, 36）
TRAIN_MIN_YEARS = 2.0  # 最小Train期間（年）
N_TRIALS = 100  # 最適化試行回数（再現性確認のため100に増加）
STUDY_TYPE = "C"  # スタディタイプ（A/B/C）
HOLDOUT_EVAL_YEAR = 2025  # 評価終了年でホールドアウトを指定
FOLD_TYPE = "roll"  # foldタイプ（roll方式）
SEED = 42  # 乱数シード（固定）
# 並列戦略: roll方式ではfold並列を有効化、Optuna並列は無効化
N_JOBS_FOLD = 1  # fold間の並列数（安定優先のため1に設定）
N_JOBS_OPTUNA = 1  # Optunaの並列数（安定優先のため1に設定）


def main():
    """Walk-Forward Analysisを実行（roll方式、n_trials=100）"""
    print("=" * 80)
    print("Walk-Forward Analysis 実行（roll方式、n_trials=100）")
    print("=" * 80)
    print()
    print("設定:")
    print(f"  期間: {START_DATE} ～ {END_DATE}")
    print(f"  ホライズン: {HORIZON}ヶ月")
    print(f"  Foldタイプ: {FOLD_TYPE}")
    print(f"  最小Train期間: {TRAIN_MIN_YEARS}年")
    print(f"  最適化試行回数: {N_TRIALS}（再現性確認のため増加）")
    print(f"  スタディタイプ: {STUDY_TYPE}")
    print(f"  評価終了年ホールドアウト: {HOLDOUT_EVAL_YEAR}")
    print(f"  乱数シード: {SEED}")
    print(f"  Fold間並列数: {N_JOBS_FOLD}")
    print(f"  Optuna並列数: {N_JOBS_OPTUNA}")
    print()
    print("【期待される成果物】")
    print("  1. walk_forward_longterm_12M_roll_evalYear2025.json（fold別 + 集計）")
    print("  2. params_by_fold.json（各foldのbest_params）")
    print("  3. params_operational.json（暫定運用パラメータ）")
    print()
    
    # 実行コマンドを構築
    cmd = [
        "python",
        "walk_forward_longterm.py",
        "--start", START_DATE,
        "--end", END_DATE,
        "--horizon", str(HORIZON),
        "--train-min-years", str(TRAIN_MIN_YEARS),
        "--n-trials", str(N_TRIALS),
        "--study-type", STUDY_TYPE,
        "--holdout-eval-year", str(HOLDOUT_EVAL_YEAR),
        "--fold-type", FOLD_TYPE,
        "--seed", str(SEED),
        "--n-jobs-fold", str(N_JOBS_FOLD),
        "--n-jobs-optuna", str(N_JOBS_OPTUNA),
    ]
    
    print("実行コマンド:")
    print(" ".join(cmd))
    print()
    print("=" * 80)
    print()
    
    # 実行
    try:
        result = subprocess.run(cmd, check=True)
        print()
        print("=" * 80)
        print("✅ 実行が正常に完了しました")
        print("=" * 80)
        return 0
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 80)
        print(f"❌ エラーが発生しました (終了コード: {e.returncode})")
        print("=" * 80)
        return e.returncode
    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print("⚠️  ユーザーによって中断されました")
        print("=" * 80)
        return 130


if __name__ == "__main__":
    sys.exit(main())









