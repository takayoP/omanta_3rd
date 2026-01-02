"""Train期間（2020-2022）での再最適化実行スクリプト

ChatGPTの提案に基づいて、Train期間（2020-2022）でStudy A/Bを実行します。

Usage:
    python run_optimization_train_period.py --n-trials 200
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_study(study_type: str, n_trials: int, n_jobs: int = -1, bt_workers: int = -1):
    """Study AまたはBを実行"""
    study_type_desc = "BB寄り・低ROE閾値" if study_type == "A" else "Value寄り・ROE閾値やや高め"
    
    print("=" * 80)
    print(f"Study {study_type} を実行します: {study_type_desc}")
    print("=" * 80)
    print()
    
    # モジュールとして実行
    cmd = [
        sys.executable,
        "-m",
        "omanta_3rd.jobs.optimize_timeseries_clustered",
        "--start", "2020-01-01",
        "--end", "2022-12-31",
        "--study-type", study_type,
        "--n-trials", str(n_trials),
        "--n-jobs", str(n_jobs),
        "--bt-workers", str(bt_workers),
    ]
    
    print(f"コマンド: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, check=False)
    
    if result.returncode != 0:
        print(f"❌ Study {study_type} の実行に失敗しました（戻り値: {result.returncode}）")
        return False
    else:
        print(f"✅ Study {study_type} の実行が完了しました")
        return True


def main():
    parser = argparse.ArgumentParser(description="Train期間（2020-2022）での再最適化実行")
    parser.add_argument("--n-trials", type=int, default=200,
                        help="各Studyの試行回数（デフォルト: 200）")
    parser.add_argument("--study", type=str, choices=["A", "B", "both"], default="both",
                        help="実行するStudy: A, B, または both（デフォルト: both）")
    parser.add_argument("--n-jobs", type=int, default=-1,
                        help="trial並列数（-1で自動、デフォルト: -1）")
    parser.add_argument("--bt-workers", type=int, default=-1,
                        help="trial内バックテストの並列数（-1で自動、デフォルト: -1）")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Train期間（2020-2022）での再最適化実行")
    print("=" * 80)
    print(f"期間: 2020-01-01 ～ 2022-12-31")
    print(f"各Studyの試行回数: {args.n_trials}")
    print(f"実行するStudy: {args.study}")
    print("=" * 80)
    print()
    
    results = {}
    
    if args.study in ["A", "both"]:
        results["A"] = run_study("A", args.n_trials, args.n_jobs, args.bt_workers)
        print()
    
    if args.study in ["B", "both"]:
        results["B"] = run_study("B", args.n_trials, args.n_jobs, args.bt_workers)
        print()
    
    # 結果サマリー
    print("=" * 80)
    print("実行結果サマリー")
    print("=" * 80)
    for study_type, success in results.items():
        status = "✅ 成功" if success else "❌ 失敗"
        print(f"Study {study_type}: {status}")
    print("=" * 80)
    
    # 全て成功した場合のみ成功とする
    if all(results.values()):
        print("\n✅ 全てのStudyの実行が完了しました")
        sys.exit(0)
    else:
        print("\n❌ 一部のStudyの実行に失敗しました")
        sys.exit(1)


if __name__ == "__main__":
    main()





