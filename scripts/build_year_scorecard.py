"""
年別スコアカード自動化（Gate3 機械化）

候補JSON群を走査し、各候補を 2020 / 2021 / 2022 の同一方式で採点して
1枚のCSVに集計する。Optunaの目的関数に手を入れる前の「候補×年×指標」の
見える化が目的。

使い方:
  python scripts/build_year_scorecard.py --candidates result1.json result2.json --cost-bps 25 --out scorecard.csv
  python scripts/build_year_scorecard.py --candidates-dir results/raw --cost-bps 25 --out scorecard.csv
  # 2022のみ評価（Stage0 地雷除去・計算節約）
  python scripts/build_year_scorecard.py --candidates result.json --years 2022 --out scorecard_2022only.csv
  # 2021のみ評価（Stage1: S120_4型を弾く。stage1_discard 列で判定）
  python scripts/build_year_scorecard.py --candidates result.json --years 2021 --out scorecard_2021only.csv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

import numpy as np
from omanta_3rd.jobs.optimize_longterm import calculate_longterm_performance
from omanta_3rd.jobs.longterm_run import StrategyParams
from omanta_3rd.jobs.optimize import EntryScoreParams
from omanta_3rd.backtest.feature_cache import FeatureCache
from omanta_3rd.jobs.batch_longterm_run import get_monthly_rebalance_dates


# ロードマップ定義: (test_year, train_end_日付, as_of_日付) 24M確保
YEAR_CONFIG = [
    (2020, "2019-12-30", "2022-12-30"),
    (2021, "2020-12-30", "2023-12-31"),
    (2022, "2021-12-30", "2024-12-31"),
]


def params_hash(normalized_params: dict) -> str:
    """normalized_params の安定ハッシュ（candidate_id 用）"""
    blob = json.dumps(normalized_params, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def load_json_meta(json_path: Path) -> dict:
    """JSONから study_type, scenario_id などのメタを取得"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "study_type": data.get("study_type"),
        "scenario_id": data.get("scenario_id"),
        "pool_size": data.get("pool_size"),
        "sector_cap": data.get("sector_cap"),
    }


def load_normalized_params(json_path: Path) -> dict:
    """最適化結果JSONから normalized_params を取得（無ければ best_trial.params から構成）"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    np_ = data.get("normalized_params", {})
    base = dict(np_) if np_ else {}
    if not base:
        bt = data.get("best_trial", {})
        params = bt.get("params", {})
        if not params:
            raise ValueError(f"No normalized_params or best_trial.params in {json_path}")
        base = {
            "w_quality": params.get("w_quality", 0.0),
            "w_value": params.get("w_value", 0.0),
            "w_growth": params.get("w_growth", 0.0),
            "w_record_high": params.get("w_record_high", 0.0),
            "w_size": params.get("w_size", 0.0),
            "w_forward_per": params.get("w_forward_per", 0.0),
            "roe_min": params.get("roe_min", 0.0),
            "liquidity_quantile_cut": params.get("liquidity_quantile_cut", 0.0),
            "rsi_base": params.get("rsi_base", 50.0),
            "rsi_max": params.get("rsi_max", 75.0),
            "bb_z_base": params.get("bb_z_base", -1.0),
            "bb_z_max": params.get("bb_z_max", 2.0),
            "bb_weight": params.get("bb_weight", 0.5),
            "rsi_weight": params.get("rsi_weight", 0.5),
            "rsi_min_width": params.get("rsi_min_width", 10.0),
            "bb_z_min_width": params.get("bb_z_min_width", 0.5),
        }
    # pool_size, sector_cap はトップレベルまたは normalized_params から
    base.setdefault("pool_size", data.get("pool_size", 80))
    base.setdefault("sector_cap", data.get("sector_cap", 4))
    return base


def create_strategy_params(normalized_params: dict) -> StrategyParams:
    return StrategyParams(
        w_quality=normalized_params.get("w_quality", 0.0),
        w_value=normalized_params.get("w_value", 0.0),
        w_growth=normalized_params.get("w_growth", 0.0),
        w_record_high=normalized_params.get("w_record_high", 0.0),
        w_size=normalized_params.get("w_size", 0.0),
        w_forward_per=normalized_params.get("w_forward_per", 0.0),
        roe_min=normalized_params.get("roe_min", 0.0),
        liquidity_quantile_cut=normalized_params.get("liquidity_quantile_cut", 0.0),
        pool_size=normalized_params.get("pool_size", 80),
        sector_cap=normalized_params.get("sector_cap", 4),
    )


def create_entry_params(normalized_params: dict) -> EntryScoreParams:
    return EntryScoreParams(
        rsi_base=normalized_params.get("rsi_base", 50.0),
        rsi_max=normalized_params.get("rsi_max", 75.0),
        bb_z_base=normalized_params.get("bb_z_base", -1.0),
        bb_z_max=normalized_params.get("bb_z_max", 2.0),
        bb_weight=normalized_params.get("bb_weight", 0.5),
        rsi_weight=normalized_params.get("rsi_weight", 0.5),
        rsi_min_width=normalized_params.get("rsi_min_width", 10.0),
        bb_z_min_width=normalized_params.get("bb_z_min_width", 0.5),
    )


def trimmed_mean_pct(arr: list[float], proportiontocut: float = 0.1) -> float:
    """上下 proportiontocut を落とした平均（%）"""
    if not arr or len(arr) < 3:
        return float(np.mean(arr)) if arr else 0.0
    a = np.array(arr, dtype=float)
    return float(np.mean(a[(a >= np.percentile(a, 100 * proportiontocut)) & (a <= np.percentile(a, 100 * (1 - proportiontocut)))]))


def evaluate_one_year(
    year: int,
    as_of_date: str,
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
    cost_bps: float,
    horizon_months: int,
    cache_dir: Path,
    bt_workers: int,
) -> dict:
    """1年分のOOS評価（test_start=Y-01-01, test_end=Y-12-31, as_of=as_of_date）"""
    test_start = f"{year}-01-01"
    test_end = f"{year}-12-31"
    rebalance_dates = get_monthly_rebalance_dates(test_start, test_end)
    if not rebalance_dates:
        return {
            "year": year,
            "median_annual_excess_return_pct": None,
            "trimmed_mean_annual_excess_return_pct": None,
            "p10_annual_excess_return_pct": None,
            "win_rate": None,
            "num_portfolios": 0,
        }
    feature_cache = FeatureCache(cache_dir=cache_dir)
    all_dates = get_monthly_rebalance_dates(rebalance_dates[0], as_of_date)
    features_dict, prices_dict = feature_cache.warm(all_dates, n_jobs=bt_workers, force_rebuild=False)
    perf = calculate_longterm_performance(
        rebalance_dates=rebalance_dates,
        strategy_params=strategy_params,
        entry_params=entry_params,
        cost_bps=cost_bps,
        n_jobs=bt_workers,
        features_dict=features_dict,
        prices_dict=prices_dict,
        horizon_months=horizon_months,
        require_full_horizon=True,
        as_of_date=as_of_date,
    )
    annual_list = perf.get("annual_excess_returns_list") or []
    trimmed = trimmed_mean_pct(annual_list) if annual_list else perf.get("median_annual_excess_return_pct", 0.0)
    return {
        "year": year,
        "median_annual_excess_return_pct": perf.get("median_annual_excess_return_pct"),
        "trimmed_mean_annual_excess_return_pct": trimmed,
        "p10_annual_excess_return_pct": perf.get("p10_annual_excess_return_pct"),
        "win_rate": perf.get("win_rate"),
        "num_portfolios": perf.get("num_portfolios", 0),
        "sector_HHI": None,  # 将来: 計算して詰める
        "sector_cap_hit_rate": None,
        "turnover_pct": None,
        "cost_drag_pct": None,
    }


def collect_candidate_paths(candidates: list[str] | None, candidates_dir: str | None) -> list[Path]:
    if candidates:
        return [Path(p).resolve() for p in candidates]
    if candidates_dir:
        d = Path(candidates_dir).resolve()
        if not d.is_dir():
            raise FileNotFoundError(f"Not a directory: {d}")
        return sorted(d.rglob("*.json"))
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="候補JSON群を 2020/2021/2022 で採点しスコアカードCSVを出力"
    )
    parser.add_argument(
        "--candidates",
        nargs="+",
        default=None,
        help="候補JSONファイルのパス（複数可）",
    )
    parser.add_argument(
        "--candidates-dir",
        type=str,
        default=None,
        help="候補JSONを再帰検索するディレクトリ（--candidates と排他）",
    )
    parser.add_argument("--cost-bps", type=float, default=25.0, help="取引コスト（bps）")
    parser.add_argument("--horizon-months", type=int, default=24, help="投資ホライズン（月）")
    parser.add_argument("--cache-dir", type=str, default="cache/features", help="特徴量キャッシュディレクトリ")
    parser.add_argument("--bt-workers", type=int, default=4, help="バックテスト並列数")
    parser.add_argument("--out", "-o", type=str, default="scorecard_year.csv", help="出力CSVパス")
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=None,
        help="評価する年（例: 2022 または 2020 2021 2022）。省略時は 2020,2021,2022 すべて。2022のみで地雷谷coarse gate用",
    )
    args = parser.parse_args()

    paths = collect_candidate_paths(args.candidates, args.candidates_dir)
    if not paths:
        print("エラー: --candidates または --candidates-dir で1件以上指定してください")
        return 1

    cache_dir = Path(args.cache_dir)
    rows: list[dict] = []

    for i, json_path in enumerate(paths):
        if not json_path.exists():
            print(f"スキップ（存在しない）: {json_path}")
            continue
        try:
            normalized_params = load_normalized_params(json_path)
            meta = load_json_meta(json_path)
        except Exception as e:
            print(f"スキップ（読込失敗）: {json_path} - {e}")
            continue
        cid = params_hash(normalized_params)
        strategy_params = create_strategy_params(normalized_params)
        entry_params = create_entry_params(normalized_params)
        print(f"[{i+1}/{len(paths)}] candidate_id={cid} ({json_path.name})")

        year_config = YEAR_CONFIG
        if args.years is not None:
            year_config = [c for c in YEAR_CONFIG if c[0] in args.years]
            if not year_config:
                print(f"  スキップ: --years {args.years} に該当する年がありません（2020/2021/2022のみ対応）")
                continue
        for year, _train_end, as_of_date in year_config:
            print(f"  評価中: year={year}, as_of={as_of_date}")
            rec = evaluate_one_year(
                year=year,
                as_of_date=as_of_date,
                strategy_params=strategy_params,
                entry_params=entry_params,
                cost_bps=args.cost_bps,
                horizon_months=args.horizon_months,
                cache_dir=cache_dir,
                bt_workers=args.bt_workers,
            )
            rec["candidate_id"] = cid
            rec["candidate_file"] = json_path.name
            rec["scenario_id"] = meta.get("scenario_id")
            rec["study_type"] = meta.get("study_type")
            # fail_reason: Gate3-pre 用の簡易判定
            reasons = []
            if rec.get("median_annual_excess_return_pct") is not None and rec["median_annual_excess_return_pct"] < -1.0:
                reasons.append(f"{rec['year']}_median<-1")
            elif rec.get("median_annual_excess_return_pct") is not None and rec["median_annual_excess_return_pct"] < 0:
                reasons.append(f"{rec['year']}_median<0")
            if rec.get("win_rate") is not None and rec["win_rate"] < 0.3:
                reasons.append(f"{rec['year']}_win_rate<0.3")
            rec["fail_reason"] = ";".join(reasons) if reasons else ""
            # Stage1（2021のみ）: S120_4型を3年採点前に弾く。median_2021<-2% or win_rate_2021<0.25 → discard
            if rec.get("year") == 2021:
                m = rec.get("median_annual_excess_return_pct")
                w = rec.get("win_rate")
                rec["stage1_discard"] = "yes" if (m is not None and m < -2.0) or (w is not None and w < 0.25) else ""
            else:
                rec["stage1_discard"] = ""
            rows.append(rec)

    if not rows:
        print("出力行が0件です")
        return 1

    # CSV出力（必須列＋オプション列）
    import csv
    fieldnames = [
        "candidate_id",
        "candidate_file",
        "scenario_id",
        "study_type",
        "year",
        "median_annual_excess_return_pct",
        "trimmed_mean_annual_excess_return_pct",
        "p10_annual_excess_return_pct",
        "win_rate",
        "num_portfolios",
        "fail_reason",
        "stage1_discard",
        "sector_HHI",
        "sector_cap_hit_rate",
        "turnover_pct",
        "cost_drag_pct",
    ]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"出力: {out_path} ({len(rows)} 行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
