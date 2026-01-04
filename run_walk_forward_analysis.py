#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Walk-Forward Analysis実行スクリプト
長期保有型のWalk-Forward検証を実行します
"""

import subprocess
import sys
from datetime import datetime

# パラメータ設定
START_DATE = "2020-01-01"
END_DATE = "2025-12-31"
HORIZON = 12  # ホライズン（月数: 12, 24, 36）
FOLDS = 1  # fold数（1: simple, 3: roll）
TRAIN_MIN_YEARS = 2.0  # 最小Train期間（年）
N_TRIALS = 50  # 最適化試行回数
STUDY_TYPE = "C"  # スタディタイプ（A/B/C）
HOLDOUT_EVAL_YEAR = 2025  # 評価終了年でホールドアウトを指定
FOLD_TYPE = "simple"  # foldタイプ（simple/roll）
SEED = 42  # 乱数シード（再現性のため）
# 並列戦略: fold並列とOptuna並列を同時に使わない
# simple方式（fold=1）の場合: fold並列は無効、Optuna並列を有効化
# roll方式（fold>1）の場合: fold並列を有効、Optuna並列は無効化
N_JOBS_FOLD = 1  # fold間の並列数（simple方式ではfold=1のため1に設定）
N_JOBS_OPTUNA = 1  # Optunaの並列数（安定優先のため1に設定）


def main():
    """Walk-Forward Analysisを実行"""
    print("=" * 80)
    print("Walk-Forward Analysis 実行")
    print("=" * 80)
    print()
    print("設定:")
    print(f"  期間: {START_DATE} ～ {END_DATE}")
    print(f"  ホライズン: {HORIZON}ヶ月")
    print(f"  Fold数: {FOLDS}")
    print(f"  最小Train期間: {TRAIN_MIN_YEARS}年")
    print(f"  最適化試行回数: {N_TRIALS}")
    print(f"  スタディタイプ: {STUDY_TYPE}")
    print(f"  評価終了年ホールドアウト: {HOLDOUT_EVAL_YEAR}")
    print(f"  Foldタイプ: {FOLD_TYPE}")
    print(f"  乱数シード: {SEED}")
    print(f"  Fold間並列数: {N_JOBS_FOLD}")
    print(f"  Optuna並列数: {N_JOBS_OPTUNA}")
    print()
    
    # 実行コマンドを構築
    cmd = [
        "python",
        "walk_forward_longterm.py",
        "--start", START_DATE,
        "--end", END_DATE,
        "--horizon", str(HORIZON),
        "--folds", str(FOLDS),
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

