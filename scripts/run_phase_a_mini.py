#!/usr/bin/env python3
"""
Phase A-mini: Study C × 5 seeds × 50 trials × 2 scenarios (S120_3, S160_3).

2段階 coarse gate 用に trial ログ（trials_log_*.jsonl）と
最適化結果 JSON を出力。Stage0（2022のみ）→ Stage1（2021のみ）→ 3年スコアカードは手動で実施。

使い方:
  python scripts/run_phase_a_mini.py
  python scripts/run_phase_a_mini.py --trials 30 --seeds 11 22 33  # 短いテスト
"""
from __future__ import annotations

import argparse
import subprocess
import sys

# ロードマップ「Step 0：シナリオ優先順位」に合わせたデフォルト
SCENARIOS = [
    {"id": "S120_3", "pool": 120, "cap": 3},
    {"id": "S160_3", "pool": 160, "cap": 3},
]
SEEDS = [11, 22, 33, 44, 55]
TRIALS = 50


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase A-mini: Study C × seeds × trials × S120_3/S160_3")
    parser.add_argument("--trials", type=int, default=TRIALS, help=f"n_trials per (seed, scenario). default={TRIALS}")
    parser.add_argument("--seeds", type=int, nargs="+", default=SEEDS, help=f"random seeds. default={SEEDS}")
    parser.add_argument("--n-jobs", type=int, default=1, help="Optuna n_jobs")
    parser.add_argument("--bt-workers", type=int, default=8, help="backtest workers")
    parser.add_argument("--dry-run", action="store_true", help="print commands only")
    args = parser.parse_args()

    base_cmd = [
        sys.executable,
        "-m",
        "omanta_3rd.jobs.optimize_longterm",
        "--study-type", "C",
        "--start", "2018-01-31",
        "--end", "2024-12-31",
        "--train-end-date", "2021-12-30",
        "--as-of-date", "2024-12-31",
        "--horizon-months", "24",
        "--cost-bps", "25",
        "--n-trials", str(args.trials),
        "--n-jobs", str(args.n_jobs),
        "--bt-workers", str(args.bt_workers),
    ]

    total = len(args.seeds) * len(SCENARIOS)
    n = 0
    for s in SCENARIOS:
        for seed in args.seeds:
            n += 1
            cmd = base_cmd + [
                "--pool-size", str(s["pool"]),
                "--sector-cap-max", str(s["cap"]),
                "--random-seed", str(seed),
            ]
            print(f"[{n}/{total}] {s['id']} seed={seed}")
            if args.dry_run:
                print("  ", " ".join(cmd))
                continue
            ret = subprocess.run(cmd)
            if ret.returncode != 0:
                print(f"  exit code {ret.returncode}", file=sys.stderr)
                sys.exit(ret.returncode)
    print("Phase A-mini 完了。Stage0/Stage1 は trials_log_*.jsonl と build_year_scorecard.py で実施。")


if __name__ == "__main__":
    main()
