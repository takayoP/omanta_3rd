"""
ポートフォリオ特性の比較分析

2021と2022の期間で、ポートフォリオ特性（選定銘柄数、業種比率、時価総額など）を比較します。
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter
import pandas as pd
import numpy as np

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from omanta_3rd.jobs.optimize_timeseries import _select_portfolio_for_rebalance_date
from omanta_3rd.jobs.longterm_run import StrategyParams
from omanta_3rd.jobs.optimize import EntryScoreParams
from omanta_3rd.backtest.feature_cache import FeatureCache
from omanta_3rd.jobs.batch_longterm_run import get_monthly_rebalance_dates
# from omanta_3rd.infra.db import connect_db  # 未使用のためコメントアウト


def load_params_from_json(json_path: Path) -> dict:
    """最適化結果JSONからパラメータを読み込む"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    normalized_params = data.get("normalized_params", {})
    
    return {
        "normalized_params": normalized_params,
    }


def create_strategy_params(normalized_params: dict) -> StrategyParams:
    """normalized_paramsからStrategyParamsを作成"""
    return StrategyParams(
        w_quality=normalized_params.get("w_quality", 0.0),
        w_value=normalized_params.get("w_value", 0.0),
        w_growth=normalized_params.get("w_growth", 0.0),
        w_record_high=normalized_params.get("w_record_high", 0.0),
        w_size=normalized_params.get("w_size", 0.0),
        w_forward_per=normalized_params.get("w_forward_per", 0.0),
        roe_min=normalized_params.get("roe_min", 0.0),
        liquidity_quantile_cut=normalized_params.get("liquidity_quantile_cut", 0.0),
    )


def create_entry_params(normalized_params: dict) -> EntryScoreParams:
    """normalized_paramsからEntryScoreParamsを作成"""
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


def analyze_portfolio_characteristics(
    portfolios: dict,  # {rebalance_date: portfolio_df}
    features_dict: dict,  # {rebalance_date: features_df}
) -> dict:
    """ポートフォリオ特性を分析"""
    all_stats = []
    
    for rebalance_date, portfolio_df in portfolios.items():
        if portfolio_df.empty:
            continue
        
        # 特徴量を取得
        feat = features_dict.get(rebalance_date)
        if feat is None or feat.empty:
            continue
        
        # ポートフォリオの銘柄コード
        portfolio_codes = set(portfolio_df.index if hasattr(portfolio_df.index, 'tolist') else portfolio_df["code"].tolist())
        
        # 特徴量から該当銘柄の情報を取得
        portfolio_features = feat[feat.index.isin(portfolio_codes) if hasattr(feat.index, 'isin') else feat["code"].isin(portfolio_codes)]
        
        if portfolio_features.empty:
            continue
        
        # 統計情報を計算
        stats = {
            "rebalance_date": rebalance_date,
            "num_stocks": len(portfolio_df),
            "avg_core_score": portfolio_df["core_score"].mean() if "core_score" in portfolio_df.columns else None,
            "avg_entry_score": portfolio_df["entry_score"].mean() if "entry_score" in portfolio_df.columns else None,
            "min_core_score": portfolio_df["core_score"].min() if "core_score" in portfolio_df.columns else None,
            "max_core_score": portfolio_df["core_score"].max() if "core_score" in portfolio_df.columns else None,
        }
        
        # 業種分布
        if "sector33" in portfolio_features.columns:
            sector_counts = portfolio_features["sector33"].value_counts().to_dict()
            stats["sector_distribution"] = sector_counts
            stats["num_sectors"] = len(sector_counts)
        
        # 時価総額
        if "market_cap" in portfolio_features.columns:
            market_caps = portfolio_features["market_cap"].dropna()
            if len(market_caps) > 0:
                stats["avg_market_cap"] = market_caps.mean()
                stats["median_market_cap"] = market_caps.median()
                stats["min_market_cap"] = market_caps.min()
                stats["max_market_cap"] = market_caps.max()
        
        # PER/PBR
        if "forward_per" in portfolio_features.columns:
            pers = portfolio_features["forward_per"].dropna()
            if len(pers) > 0:
                stats["avg_per"] = pers.mean()
                stats["median_per"] = pers.median()
        
        if "pbr" in portfolio_features.columns:
            pbrs = portfolio_features["pbr"].dropna()
            if len(pbrs) > 0:
                stats["avg_pbr"] = pbrs.mean()
                stats["median_pbr"] = pbrs.median()
        
        # ROE
        if "roe" in portfolio_features.columns:
            roes = portfolio_features["roe"].dropna()
            if len(roes) > 0:
                stats["avg_roe"] = roes.mean()
                stats["median_roe"] = roes.median()
        
        all_stats.append(stats)
    
    return all_stats


def compare_period_characteristics(stats_2022: list, stats_2021: list) -> None:
    """期間間のポートフォリオ特性を比較"""
    print("=" * 80)
    print("【ポートフォリオ特性の比較】")
    print("=" * 80)
    print()
    
    # 基本統計
    print("【基本統計】")
    print(f"{'指標':<30} {'2022':<20} {'2021':<20} {'差分':<20}")
    print("-" * 90)
    
    avg_stocks_2022 = np.mean([s["num_stocks"] for s in stats_2022])
    avg_stocks_2021 = np.mean([s["num_stocks"] for s in stats_2021])
    print(f"{'平均選定銘柄数':<30} {avg_stocks_2022:<20.1f} {avg_stocks_2021:<20.1f} {avg_stocks_2022 - avg_stocks_2021:<20.1f}")
    
    if stats_2022 and "avg_core_score" in stats_2022[0] and stats_2022[0]["avg_core_score"] is not None:
        avg_core_2022 = np.mean([s["avg_core_score"] for s in stats_2022 if s.get("avg_core_score") is not None])
        avg_core_2021 = np.mean([s["avg_core_score"] for s in stats_2021 if s.get("avg_core_score") is not None])
        print(f"{'平均Coreスコア':<30} {avg_core_2022:<20.4f} {avg_core_2021:<20.4f} {avg_core_2022 - avg_core_2021:<20.4f}")
    
    if stats_2022 and "avg_entry_score" in stats_2022[0] and stats_2022[0]["avg_entry_score"] is not None:
        avg_entry_2022 = np.mean([s["avg_entry_score"] for s in stats_2022 if s.get("avg_entry_score") is not None])
        avg_entry_2021 = np.mean([s["avg_entry_score"] for s in stats_2021 if s.get("avg_entry_score") is not None])
        print(f"{'平均Entryスコア':<30} {avg_entry_2022:<20.4f} {avg_entry_2021:<20.4f} {avg_entry_2022 - avg_entry_2021:<20.4f}")
    
    if stats_2022 and "avg_market_cap" in stats_2022[0] and stats_2022[0]["avg_market_cap"] is not None:
        avg_mcap_2022 = np.mean([s["avg_market_cap"] for s in stats_2022 if s.get("avg_market_cap") is not None])
        avg_mcap_2021 = np.mean([s["avg_market_cap"] for s in stats_2021 if s.get("avg_market_cap") is not None])
        print(f"{'平均時価総額（億円）':<30} {avg_mcap_2022/1e8:<20.2f} {avg_mcap_2021/1e8:<20.2f} {(avg_mcap_2022 - avg_mcap_2021)/1e8:<20.2f}")
    
    print()
    
    # 業種分布
    print("【業種分布（上位5業種）】")
    print()
    
    # 2022の業種分布を集計
    sector_counts_2022 = Counter()
    for s in stats_2022:
        if "sector_distribution" in s:
            sector_counts_2022.update(s["sector_distribution"])
    
    # 2021の業種分布を集計
    sector_counts_2021 = Counter()
    for s in stats_2021:
        if "sector_distribution" in s:
            sector_counts_2021.update(s["sector_distribution"])
    
    # 上位5業種を表示
    top_sectors = set(list(sector_counts_2022.keys())[:5] + list(sector_counts_2021.keys())[:5])
    
    print(f"{'業種':<30} {'2022':<20} {'2021':<20} {'差分':<20}")
    print("-" * 90)
    for sector in sorted(top_sectors, key=lambda x: sector_counts_2022.get(x, 0) + sector_counts_2021.get(x, 0), reverse=True)[:10]:
        count_2022 = sector_counts_2022.get(sector, 0)
        count_2021 = sector_counts_2021.get(sector, 0)
        print(f"{sector:<30} {count_2022:<20} {count_2021:<20} {count_2022 - count_2021:<20}")
    
    print()


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ポートフォリオ特性の比較分析")
    parser.add_argument("--params-json", type=str, required=True,
                       help="最適化結果JSONファイルのパス")
    parser.add_argument("--test-periods", type=str, default="2022,2021",
                       help="評価する期間（カンマ区切り、デフォルト: 2022,2021）")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("ポートフォリオ特性の比較分析")
    print("=" * 80)
    print()
    
    # パラメータを読み込む
    json_path = Path(args.params_json)
    if not json_path.exists():
        print(f"❌ エラー: {json_path} が見つかりません")
        return 1
    
    print(f"📄 パラメータを読み込み中: {json_path}")
    data = load_params_from_json(json_path)
    normalized_params = data["normalized_params"]
    
    # 期間の定義
    test_periods_config = {
        "2022": {
            "test_start_date": "2022-01-31",
            "test_end_date": "2022-12-30",
        },
        "2021": {
            "test_start_date": "2021-01-31",
            "test_end_date": "2021-12-30",
        },
        "2020": {
            "test_start_date": "2020-01-31",
            "test_end_date": "2020-12-30",
        },
    }
    
    test_periods = [p.strip() for p in args.test_periods.split(",")]
    
    # 各期間のtest_datesを取得
    test_dates_dict = {}
    for period in test_periods:
        if period not in test_periods_config:
            print(f"❌ エラー: 期間 '{period}' は定義されていません")
            print(f"   利用可能な期間: {list(test_periods_config.keys())}")
            return 1
        
        config = test_periods_config[period]
        test_dates = get_monthly_rebalance_dates(config["test_start_date"], config["test_end_date"])
        test_dates_dict[period] = {
            "test_dates": test_dates,
        }
    
    print(f"📅 評価期間: {', '.join(test_periods)}")
    print()
    
    # パラメータを作成
    strategy_params = create_strategy_params(normalized_params)
    entry_params = create_entry_params(normalized_params)
    
    # 特徴量キャッシュを構築
    print("=" * 80)
    print("特徴量キャッシュを構築中...")
    print("=" * 80)
    cache_dir = Path("cache/features")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    
    all_rebalance_dates = []
    for period_data in test_dates_dict.values():
        all_rebalance_dates.extend(period_data["test_dates"])
    
    all_rebalance_dates = sorted(list(set(all_rebalance_dates)))
    
    features_dict, prices_dict = feature_cache.warm(
        all_rebalance_dates,
        n_jobs=4,
        force_rebuild=False,
    )
    print(f"   特徴量: {len(features_dict)}日分")
    print(f"   価格データ: {len(prices_dict)}日分")
    print()
    
    # 各期間でポートフォリオを選定
    print("=" * 80)
    print("各期間でポートフォリオを選定中...")
    print("=" * 80)
    print()
    
    period_portfolios = {}
    period_stats = {}
    
    strategy_params_dict = {
        field.name: getattr(strategy_params, field.name)
        for field in StrategyParams.__dataclass_fields__.values()
    }
    entry_params_dict = {
        field.name: getattr(entry_params, field.name)
        for field in EntryScoreParams.__dataclass_fields__.values()
    }
    
    for period in test_periods:
        period_data = test_dates_dict[period]
        test_dates = period_data["test_dates"]
        
        print(f"【期間: {period}】")
        print("-" * 80)
        
        portfolios = {}
        for rebalance_date in test_dates:
            portfolio = _select_portfolio_for_rebalance_date(
                rebalance_date,
                strategy_params_dict,
                entry_params_dict,
                features_dict.get(rebalance_date),
                prices_dict.get(rebalance_date),
            )
            if portfolio is not None and not portfolio.empty:
                portfolios[rebalance_date] = portfolio
        
        period_portfolios[period] = portfolios
        
        # ポートフォリオ特性を分析
        stats = analyze_portfolio_characteristics(portfolios, features_dict)
        period_stats[period] = stats
        
        print(f"  ポートフォリオ数: {len(portfolios)}")
        if stats:
            print(f"  平均選定銘柄数: {np.mean([s['num_stocks'] for s in stats]):.1f}")
        print()
    
    # 期間比較
    if "2022" in period_stats and "2021" in period_stats:
        compare_period_characteristics(period_stats["2022"], period_stats["2021"])
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
