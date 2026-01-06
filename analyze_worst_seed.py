"""
ワーストseedの詳細分析

seed=4の各テスト月ごとの超過年率、市場（TOPIX）の年率、
選ばれた銘柄の特徴量分布を分析します。

Usage:
    python analyze_worst_seed.py \
        --json-file seed_robustness_test_result.json \
        --seed 4
"""

import argparse
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime as dt
from dataclasses import replace

from omanta_3rd.jobs.optimize_longterm import (
    get_monthly_rebalance_dates,
    EntryScoreParams,
)
from omanta_3rd.jobs.longterm_run import StrategyParams
from omanta_3rd.backtest.feature_cache import FeatureCache
from omanta_3rd.backtest.performance import calculate_portfolio_performance
from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.optimize import _select_portfolio_with_params
from omanta_3rd.jobs.longterm_run import save_portfolio


def load_best_params(json_file: str) -> Dict[str, Any]:
    """JSONファイルから最良パラメータを読み込む"""
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return data["best_trial"]["params"]


def build_params_from_json(params_dict: Dict[str, float]) -> tuple[StrategyParams, EntryScoreParams]:
    """JSONから読み込んだパラメータからStrategyParamsとEntryScoreParamsを構築"""
    # 重みパラメータを正規化
    w_quality = params_dict["w_quality"]
    w_value = params_dict["w_value"]
    w_growth = params_dict["w_growth"]
    w_record_high = params_dict["w_record_high"]
    w_size = params_dict["w_size"]
    
    total = w_quality + w_value + w_growth + w_record_high + w_size
    if total > 0:
        w_quality /= total
        w_value /= total
        w_growth /= total
        w_record_high /= total
        w_size /= total
    
    # StrategyParamsを構築
    default_params = StrategyParams()
    strategy_params = replace(
        default_params,
        target_min=12,
        target_max=12,
        w_quality=w_quality,
        w_value=w_value,
        w_growth=w_growth,
        w_record_high=w_record_high,
        w_size=w_size,
        w_forward_per=params_dict["w_forward_per"],
        w_pbr=1.0 - params_dict["w_forward_per"],
        roe_min=params_dict["roe_min"],
        liquidity_quantile_cut=params_dict["liquidity_quantile_cut"],
    )
    
    # EntryScoreParamsを構築
    entry_params = EntryScoreParams(
        rsi_base=params_dict["rsi_base"],
        rsi_max=params_dict["rsi_max"],
        bb_z_base=params_dict["bb_z_base"],
        bb_z_max=params_dict["bb_z_max"],
        bb_weight=params_dict["bb_weight"],
        rsi_weight=1.0 - params_dict["bb_weight"],
        rsi_min_width=params_dict.get("rsi_min_width", 10.0),  # デフォルト: 10.0（緩和済み）
        bb_z_min_width=params_dict.get("bb_z_min_width", 0.5),  # デフォルト: 0.5（緩和済み）
    )
    
    return strategy_params, entry_params


def analyze_worst_seed(
    seed_robustness_json: str,
    seed: int,
    json_file: str,
    start_date: str,
    end_date: str,
    cache_dir: str = "cache/features",
) -> None:
    """
    ワーストseedの詳細分析
    
    Args:
        seed_robustness_json: seed耐性テスト結果のJSONファイル
        seed: 分析するseed番号
        json_file: 最良パラメータを含むJSONファイル
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        cache_dir: キャッシュディレクトリ
    """
    print("=" * 80)
    print(f"ワーストseed={seed}の詳細分析")
    print("=" * 80)
    print()
    
    # seed耐性テスト結果を読み込む
    with open(seed_robustness_json, "r", encoding="utf-8") as f:
        robustness_data = json.load(f)
    
    # 指定されたseedの詳細を取得
    seed_detail = None
    for detail in robustness_data.get("seed_details", []):
        if detail["seed"] == seed:
            seed_detail = detail
            break
    
    if seed_detail is None:
        raise ValueError(f"Seed {seed} not found in robustness test results")
    
    test_dates = seed_detail["test_dates"]
    print(f"テストデータ日数: {len(test_dates)}日")
    print(f"テストデータ: {test_dates}")
    print()
    
    # 最良パラメータを読み込む
    best_params = load_best_params(json_file)
    strategy_params, entry_params = build_params_from_json(best_params)
    
    # 特徴量キャッシュを読み込む
    feature_cache = FeatureCache(cache_dir=cache_dir)
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    features_dict, prices_dict = feature_cache.warm(rebalance_dates, n_jobs=-1)
    
    # 最新日を取得（テストデータの最後の日付から推定）
    # 実際には、calculate_portfolio_performanceが使用する最新日を確認する必要がある
    # ここでは、end_date以降のデータも必要なので、より後の日付を使用
    # 実際の実装では、calculate_portfolio_performanceが使用する最新日を確認
    with connect_db() as conn:
        latest_date_df = pd.read_sql_query(
            "SELECT MAX(date) AS max_date FROM prices_daily",
            conn
        )
        latest_date = latest_date_df["max_date"].iloc[0] if not latest_date_df.empty else end_date
    
    print(f"評価最新日: {latest_date}")
    print()
    
    # 各テスト月ごとの詳細を分析
    print("=" * 80)
    print("各テスト月ごとの詳細分析")
    print("=" * 80)
    print()
    
    monthly_results = []
    
    for test_date in sorted(test_dates):
        print(f"[{test_date}]")
        
        # ポートフォリオを選定（最適化時と同じパラメータを使用）
        
        # 特徴量を取得
        if test_date not in features_dict:
            print(f"  警告: {test_date}の特徴量が見つかりません")
            continue
        
        features_df = features_dict[test_date]
        
        # ポートフォリオを選定
        portfolio_df = _select_portfolio_with_params(
            features_df,
            strategy_params,
            entry_params,
        )
        
        if portfolio_df.empty:
            print(f"  警告: {test_date}のポートフォリオが空です")
            continue
        
        print(f"  ポートフォリオ銘柄数: {len(portfolio_df)}")
        
        # ポートフォリオを一時的にデータベースに保存（calculate_portfolio_performanceがDBから読み込むため）
        with connect_db() as conn:
            save_portfolio(conn, portfolio_df)
            conn.commit()
            
            # パフォーマンスを計算
            perf = calculate_portfolio_performance(
                rebalance_date=test_date,
                as_of_date=latest_date,
                portfolio_table="portfolio_monthly",
            )
            
            # 一時的に保存したポートフォリオを削除
            conn.execute(
                "DELETE FROM portfolio_monthly WHERE rebalance_date = ?",
                (test_date,)
            )
            conn.commit()
        
        if "error" in perf:
            print(f"  エラー: {perf['error']}")
            continue
        
        # 保有期間を計算
        rebalance_dt = dt.strptime(test_date, "%Y-%m-%d")
        latest_dt = dt.strptime(latest_date, "%Y-%m-%d")
        holding_years = (latest_dt - rebalance_dt).days / 365.25
        
        # 年率超過リターンを計算
        total_return_pct = perf.get("total_return_pct")
        topix_comparison = perf.get("topix_comparison", {})
        topix_return_pct = topix_comparison.get("topix_return_pct")
        excess_return_pct = topix_comparison.get("excess_return_pct")
        
        annual_return_pct = None
        annual_topix_return_pct = None
        annual_excess_return_pct = None
        
        if total_return_pct is not None and not pd.isna(total_return_pct) and holding_years > 0:
            return_factor = 1 + total_return_pct / 100
            if return_factor > 0:
                annual_return_pct = (return_factor ** (1 / holding_years) - 1) * 100
        
        if topix_return_pct is not None and not pd.isna(topix_return_pct) and holding_years > 0:
            topix_factor = 1 + topix_return_pct / 100
            if topix_factor > 0:
                annual_topix_return_pct = (topix_factor ** (1 / holding_years) - 1) * 100
        
        if excess_return_pct is not None and not pd.isna(excess_return_pct) and holding_years > 0:
            excess_factor = 1 + excess_return_pct / 100
            if excess_factor > 0:
                annual_excess_return_pct = (excess_factor ** (1 / holding_years) - 1) * 100
        
        # ポートフォリオの特徴量分布を計算
        portfolio_codes = portfolio_df["code"].tolist()
        portfolio_features = features_df[features_df["code"].isin(portfolio_codes)].copy()
        
        feature_stats = {}
        if not portfolio_features.empty:
            # value関連
            if "pbr" in portfolio_features.columns:
                feature_stats["pbr_median"] = portfolio_features["pbr"].median()
            if "forward_per" in portfolio_features.columns:
                feature_stats["forward_per_median"] = portfolio_features["forward_per"].median()
            
            # size関連
            if "market_cap" in portfolio_features.columns:
                feature_stats["market_cap_median"] = portfolio_features["market_cap"].median()
            
            # quality関連
            if "roe" in portfolio_features.columns:
                feature_stats["roe_median"] = portfolio_features["roe"].median()
        
        monthly_result = {
            "rebalance_date": test_date,
            "holding_years": holding_years,
            "num_stocks": len(portfolio_df),
            "total_return_pct": total_return_pct,
            "topix_return_pct": topix_return_pct,
            "excess_return_pct": excess_return_pct,
            "annual_return_pct": annual_return_pct,
            "annual_topix_return_pct": annual_topix_return_pct,
            "annual_excess_return_pct": annual_excess_return_pct,
            "feature_stats": feature_stats,
        }
        monthly_results.append(monthly_result)
        
        # 結果を表示
        print(f"  保有期間: {holding_years:.2f}年")
        print(f"  累積リターン: {total_return_pct:.2f}%" if total_return_pct is not None else "  累積リターン: N/A")
        print(f"  TOPIX累積リターン: {topix_return_pct:.2f}%" if topix_return_pct is not None else "  TOPIX累積リターン: N/A")
        print(f"  累積超過リターン: {excess_return_pct:.2f}%" if excess_return_pct is not None else "  累積超過リターン: N/A")
        if annual_return_pct is not None:
            print(f"  年率リターン: {annual_return_pct:.2f}%")
        if annual_topix_return_pct is not None:
            print(f"  TOPIX年率リターン: {annual_topix_return_pct:.2f}%")
        if annual_excess_return_pct is not None:
            print(f"  年率超過リターン: {annual_excess_return_pct:.2f}%")
        print()
    
    # 結果をまとめて表示
    print("=" * 80)
    print("【まとめ】")
    print("=" * 80)
    print()
    
    # 年別の集計
    year_stats = {}
    for result in monthly_results:
        year = dt.strptime(result["rebalance_date"], "%Y-%m-%d").year
        if year not in year_stats:
            year_stats[year] = []
        if result["annual_excess_return_pct"] is not None:
            year_stats[year].append(result["annual_excess_return_pct"])
    
    print("年別の年率超過リターン（平均）:")
    for year in sorted(year_stats.keys()):
        avg = np.mean(year_stats[year]) if year_stats[year] else None
        count = len(year_stats[year])
        print(f"  {year}年: {avg:.2f}% ({count}ポートフォリオ)" if avg is not None else f"  {year}年: N/A ({count}ポートフォリオ)")
    print()
    
    # 結果をJSONに保存
    output_file = f"worst_seed_{seed}_analysis.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "seed": seed,
            "test_dates": test_dates,
            "latest_date": latest_date,
            "monthly_results": monthly_results,
            "year_stats": {str(k): {
                "mean": float(np.mean(v)) if v else None,
                "count": len(v)
            } for k, v in year_stats.items()},
        }, f, indent=2, ensure_ascii=False)
    
    print(f"詳細分析結果を保存しました: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ワーストseedの詳細分析"
    )
    parser.add_argument(
        "--seed-robustness-json",
        type=str,
        default="seed_robustness_test_result.json",
        help="seed耐性テスト結果のJSONファイル",
    )
    parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="分析するseed番号",
    )
    parser.add_argument(
        "--json-file",
        type=str,
        default="optimization_result_optimization_longterm_studyC_20260102_205614.json",
        help="最良パラメータを含むJSONファイル",
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2020-01-01",
        help="開始日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2022-12-31",
        help="終了日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default="cache/features",
        help="キャッシュディレクトリ",
    )
    
    args = parser.parse_args()
    
    analyze_worst_seed(
        seed_robustness_json=args.seed_robustness_json,
        seed=args.seed,
        json_file=args.json_file,
        start_date=args.start,
        end_date=args.end,
        cache_dir=args.cache_dir,
    )

