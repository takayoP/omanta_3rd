#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Walk-Forward Analysis診断スクリプト
1 trialの実行時間を測定して、A/Bパターンを特定します
"""

import subprocess
import sys
from datetime import datetime

# パラメータ設定（診断用：最小限の設定）
START_DATE = "2020-01-01"
END_DATE = "2025-12-31"
HORIZON = 12  # ホライズン（月数: 12, 24, 36）
FOLDS = 1  # fold数（1: simple, 3: roll）
TRAIN_MIN_YEARS = 2.0  # 最小Train期間（年）
N_TRIALS = 1  # 診断用：1 trialのみ
STUDY_TYPE = "C"  # スタディタイプ（A/B/C）
HOLDOUT_EVAL_YEAR = 2025  # 評価終了年でホールドアウトを指定
FOLD_TYPE = "simple"  # foldタイプ（simple/roll）
SEED = 42  # 乱数シード（再現性のため）
# 診断用：Optuna並列は無効化（1 trialの実行時間を正確に測定）
N_JOBS_FOLD = 1  # fold間の並列数
N_JOBS_OPTUNA = 1  # Optunaの並列数（診断用：1に設定）


def main():
    """Walk-Forward Analysisを診断実行"""
    print("=" * 80)
    print("Walk-Forward Analysis 診断実行")
    print("=" * 80)
    print()
    print("【診断目的】")
    print("  1 trialの実行時間を測定して、A/Bパターンを特定します")
    print("  A: 1 trialが極端に重い（数十分〜）")
    print("  B: objectiveが待ち/ハング（ロック・I/O待ち・無限ループ等）")
    print()
    print("設定:")
    print(f"  期間: {START_DATE} ～ {END_DATE}")
    print(f"  ホライズン: {HORIZON}ヶ月")
    print(f"  Fold数: {FOLDS}")
    print(f"  最小Train期間: {TRAIN_MIN_YEARS}年")
    print(f"  最適化試行回数: {N_TRIALS} (診断用)")
    print(f"  スタディタイプ: {STUDY_TYPE}")
    print(f"  評価終了年ホールドアウト: {HOLDOUT_EVAL_YEAR}")
    print(f"  Foldタイプ: {FOLD_TYPE}")
    print(f"  乱数シード: {SEED}")
    print(f"  Fold間並列数: {N_JOBS_FOLD}")
    print(f"  Optuna並列数: {N_JOBS_OPTUNA} (診断用：1に設定)")
    print()
    print("【確認ポイント】")
    print("  1. '[Trial 0] objective開始...' のログが表示されるか")
    print("  2. '[Trial 0] 完了: value=..., 時間=...秒' が表示されるまでの時間")
    print("  3. 30秒以内なら正常、5分以上ならAパターン（重い）")
    print("  4. '[Trial 0] objective開始...' が出ないならBパターン（ハング）")
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
    
    # 実行開始時刻を記録
    start_time = datetime.now()
    print(f"実行開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 実行
    try:
        result = subprocess.run(cmd, check=True)
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        print()
        print("=" * 80)
        print("✅ 診断実行が正常に完了しました")
        print(f"  実行開始: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  実行終了: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  総実行時間: {elapsed:.1f}秒 ({elapsed/60:.1f}分)")
        print("=" * 80)
        print()
        print("【診断結果の解釈】")
        if elapsed < 30:
            print("  ✓ 1 trialが30秒以内：正常（50 trialsでも現実的）")
        elif elapsed < 300:
            print("  ⚠️  1 trialが5分以内：やや重い（50 trialsで約4時間）")
        else:
            print("  ❌ 1 trialが5分以上：非常に重い（Aパターン、pruner/列削減が必要）")
        return 0
    except subprocess.CalledProcessError as e:
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        print()
        print("=" * 80)
        print(f"❌ エラーが発生しました (終了コード: {e.returncode})")
        print(f"  実行時間: {elapsed:.1f}秒 ({elapsed/60:.1f}分)")
        print("=" * 80)
        print()
        print("【診断結果の解釈】")
        print("  ❌ エラーが発生：ログを確認して、Bパターン（ハング/ロック）の可能性")
        return e.returncode
    except KeyboardInterrupt:
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        print()
        print("=" * 80)
        print("⚠️  ユーザーによって中断されました")
        print(f"  実行時間: {elapsed:.1f}秒 ({elapsed/60:.1f}分)")
        print("=" * 80)
        print()
        print("【診断結果の解釈】")
        if elapsed < 30:
            print("  ✓ 中断前まで正常に動作していた可能性")
        else:
            print("  ⚠️  長時間実行されていた：Aパターン（重い）の可能性")
        return 130


if __name__ == "__main__":
    sys.exit(main())


