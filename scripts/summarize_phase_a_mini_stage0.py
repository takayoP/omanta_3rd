#!/usr/bin/env python3
"""
Phase A-mini の 10 本の optimization_result_*.json を一括読みし、
Stage0（2022 粗ゲート）通過本数と通過 run（scenario_id / seed）をまとめる。

Stage0 基準: median_2022 >= -5% かつ win_rate_2022 >= 0.20
（test_performance が 2022 リバランス評価なのでそれを使用）

使い方:
  python scripts/summarize_phase_a_mini_stage0.py
  python scripts/summarize_phase_a_mini_stage0.py --dir .
  python scripts/summarize_phase_a_mini_stage0.py --dir . --pattern "optimization_result_*studyC*.json"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Stage0 基準（ロードマップ準拠）
STAGE0_MEDIAN_MIN = -5.0   # %
STAGE0_WIN_RATE_MIN = 0.20


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase A-mini 結果 JSON を読み、Stage0 通過本数・通過 run をまとめる"
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=".",
        help="JSON を探すディレクトリ（デフォルト: カレント）",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="optimization_result_optimization_longterm_studyC_*.json",
        help="検索する JSON の glob パターン",
    )
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.is_dir():
        print(f"エラー: ディレクトリが存在しません: {root}", file=sys.stderr)
        sys.exit(1)

    files = sorted(root.glob(args.pattern))
    if not files:
        print(f"警告: 該当 JSON がありません: {root / args.pattern}", file=sys.stderr)
        print("  --dir でプロジェクトルートを指定してください。")
        sys.exit(0)

    rows = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"スキップ（読めません）: {path.name} - {e}", file=sys.stderr)
            continue

        tp = data.get("test_performance") or {}
        median = tp.get("median_annual_excess_return_pct")
        win_rate = tp.get("win_rate")
        scenario_id = data.get("scenario_id") or data.get("pool_size") and data.get("sector_cap") and f"S{data['pool_size']}_{data['sector_cap']}" or "-"
        if scenario_id == "-" and "pool_size" in data:
            scenario_id = f"S{data.get('pool_size', '?')}_{data.get('sector_cap', '?')}"
        seed = data.get("random_seed")

        if median is None and win_rate is None and tp.get("by_year"):
            by_2022 = (tp.get("by_year") or {}).get("2022") or {}
            median = by_2022.get("median_annual_excess_return_pct")
            win_rate = by_2022.get("win_rate")

        passed = (
            median is not None
            and win_rate is not None
            and median >= STAGE0_MEDIAN_MIN
            and win_rate >= STAGE0_WIN_RATE_MIN
        )
        rows.append({
            "file": path.name,
            "path": str(path),
            "scenario_id": scenario_id,
            "seed": seed,
            "median_2022": median,
            "win_rate_2022": win_rate,
            "passed": passed,
        })

    passed_list = [r for r in rows if r["passed"]]
    failed_list = [r for r in rows if not r["passed"]]

    # 出力
    print("=" * 60)
    print("Phase A-mini Stage0 サマリ")
    print("=" * 60)
    print(f"対象 JSON 数:     {len(rows)}")
    print(f"Stage0 通過本数: {len(passed_list)}")
    print(f"Stage0 不合格:   {len(failed_list)}")
    print(f"基準: median_2022 >= {STAGE0_MEDIAN_MIN}% , win_rate_2022 >= {STAGE0_WIN_RATE_MIN}")
    print()

    if passed_list:
        print("【Stage0 通過 run】")
        print(f"  {'scenario_id':<10} {'seed':>6}  {'median_2022':>10}  {'win_rate_2022':>12}  file")
        print("  " + "-" * 70)
        for r in passed_list:
            m = r["median_2022"] if r["median_2022"] is not None else "-"
            w = r["win_rate_2022"] if r["win_rate_2022"] is not None else "-"
            if isinstance(m, float):
                m = f"{m:.2f}"
            if isinstance(w, float):
                w = f"{w:.2f}"
            sid = r["scenario_id"] if r["scenario_id"] is not None else "-"
            seed_val = r["seed"] if r["seed"] is not None else "-"
            print(f"  {str(sid):<10} {str(seed_val):>6}  {str(m):>10}  {str(w):>12}  {r['file']}")
        print()
    else:
        print("【Stage0 通過 run】なし")
        print()

    print("【全 run 一覧（不合格含む）】")
    print(f"  {'scenario_id':<10} {'seed':>6}  {'median_2022':>10}  {'win_rate_2022':>12}  pass  file")
    print("  " + "-" * 75)
    for r in rows:
        m = r["median_2022"] if r["median_2022"] is not None else "null"
        w = r["win_rate_2022"] if r["win_rate_2022"] is not None else "null"
        if isinstance(m, float):
            m = f"{m:.2f}"
        if isinstance(w, float):
            w = f"{w:.2f}"
        ok = "OK" if r["passed"] else "-"
        sid = r["scenario_id"] if r["scenario_id"] is not None else "-"
        seed_val = r["seed"] if r["seed"] is not None else "-"
        print(f"  {str(sid):<10} {str(seed_val):>6}  {str(m):>10}  {str(w):>12}  {ok:>2}  {r['file']}")

    print()
    print("次: 通過 run の JSON を build_year_scorecard.py --years 2021 で Stage1 → 通過分だけ 3 年スコアカード。")


if __name__ == "__main__":
    main()
