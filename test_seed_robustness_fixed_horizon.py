"""
固定ホライズン版 seed耐性テスト

12M/24M/36Mの各ホライズンでseed耐性テストを実施します。
評価方法を「リバランス日→最新日」から「リバランス日→リバランス日+Hヶ月」に変更します。

Usage:
    python test_seed_robustness_fixed_horizon.py \
        --json-file optimization_result_optimization_longterm_studyC_20260102_205614.json \
        --start 2020-01-01 \
        --end 2022-12-31 \
        --horizon 12 \
        --n-seeds 20 \
        --train-ratio 0.8
"""

import argparse
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
from dataclasses import replace

from omanta_3rd.jobs.optimize_longterm import (
    split_rebalance_dates,
    get_monthly_rebalance_dates,
    EntryScoreParams,
)
from omanta_3rd.jobs.monthly_run import StrategyParams
from omanta_3rd.backtest.feature_cache import FeatureCache
from omanta_3rd.backtest.performance import calculate_portfolio_performance
from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.optimize import _select_portfolio_with_params
from omanta_3rd.jobs.monthly_run import save_portfolio


# 並列化用のグローバル関数（pickle可能にするため）
def _process_single_seed_wrapper(
    seed: int,
    rebalance_dates: List[str],
    train_ratio: float,
    horizon_months: int,
    cost_bps: float,
    strategy_params_dict: Dict[str, Any],
    entry_params_dict: Dict[str, Any],
    features_dict: Dict[str, pd.DataFrame],
    prices_dict: Dict[str, Dict[str, List[float]]],
) -> tuple[int, Optional[float], Optional[dict]]:
    """単一seedの処理（並列化用ラッパー）"""
    from omanta_3rd.jobs.optimize_longterm import split_rebalance_dates
    from omanta_3rd.jobs.monthly_run import StrategyParams
    from omanta_3rd.jobs.optimize import EntryScoreParams
    from dataclasses import fields, replace
    
    # dataclassを復元
    default_strategy = StrategyParams()
    strategy_params = replace(
        default_strategy,
        **{k: v for k, v in strategy_params_dict.items() if hasattr(default_strategy, k)}
    )
    entry_params = EntryScoreParams(**entry_params_dict)
    
    # データ分割
    train_dates, test_dates = split_rebalance_dates(
        rebalance_dates,
        train_ratio=train_ratio,
        random_seed=seed,
    )
    
    # テストデータでパフォーマンスを計算（固定ホライズン）
    try:
        test_perf = calculate_fixed_horizon_performance(
            test_dates,
            strategy_params,
            entry_params,
            horizon_months=horizon_months,
            cost_bps=cost_bps,
            features_dict=features_dict,
            prices_dict=prices_dict,
        )
        
        test_mean_excess_ann = test_perf["mean_annual_excess_return_pct"]
        
        seed_detail = {
            "seed": seed,
            "train_dates": train_dates,
            "test_dates": test_dates,
            "test_mean_annual_excess_return_pct": test_mean_excess_ann,
            "test_median_annual_excess_return_pct": test_perf.get("median_annual_excess_return_pct", None),
            "test_mean_annual_return_pct": test_perf.get("mean_annual_return_pct", None),
            "test_win_rate": test_perf.get("win_rate", None),
            "test_num_portfolios": test_perf.get("num_portfolios", None),
        }
        
        return seed, test_mean_excess_ann, seed_detail
    except Exception as e:
        import traceback
        print(f"  [Seed {seed}] エラー: {e}")
        traceback.print_exc()
        return seed, None, None


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
    )
    
    return strategy_params, entry_params


def calculate_fixed_horizon_performance(
    rebalance_dates: List[str],
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
    horizon_months: int,
    cost_bps: float = 0.0,
    features_dict: Optional[Dict[str, pd.DataFrame]] = None,
    prices_dict: Optional[Dict[str, Dict[str, List[float]]]] = None,
) -> Dict[str, Any]:
    """
    固定ホライズン版のパフォーマンスを計算
    
    Args:
        rebalance_dates: リバランス日のリスト
        strategy_params: StrategyParams
        entry_params: EntryScoreParams
        horizon_months: ホライズン（月数、例：12, 24, 36）
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        features_dict: 特徴量辞書（{rebalance_date: features_df}）
        prices_dict: 価格データ辞書（{rebalance_date: {code: [adj_close, ...]}}）
    
    Returns:
        パフォーマンス指標の辞書
    """
    from omanta_3rd.jobs.optimize_timeseries import _run_single_backtest_portfolio_only
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from dataclasses import fields
    
    # 最新の評価日を取得
    with connect_db() as conn:
        latest_date_df = pd.read_sql_query(
            "SELECT MAX(date) as max_date FROM prices_daily",
            conn
        )
        latest_date = latest_date_df["max_date"].iloc[0] if not latest_date_df.empty else None
    
    if latest_date is None:
        raise RuntimeError("No price data available")
    
    # dataclassを辞書に変換（pickle可能にするため）
    strategy_params_dict = {
        field.name: getattr(strategy_params, field.name)
        for field in fields(StrategyParams)
    }
    entry_params_dict = {
        field.name: getattr(entry_params, field.name)
        for field in fields(EntryScoreParams)
    }
    
    portfolios = {}  # {rebalance_date: portfolio_df}
    
    # ポートフォリオを選定
    for rebalance_date in rebalance_dates:
        if rebalance_date not in features_dict:
            continue
        
        features_df = features_dict[rebalance_date]
        portfolio = _run_single_backtest_portfolio_only(
            rebalance_date,
            strategy_params_dict,
            entry_params_dict,
            features_df,
            prices_dict.get(rebalance_date) if prices_dict else None,
        )
        if portfolio is not None and not portfolio.empty:
            portfolios[rebalance_date] = portfolio
    
    if not portfolios:
        raise RuntimeError("No portfolios were generated")
    
    # 各ポートフォリオのパフォーマンスを計算（固定ホライズン）
    performances = []
    annual_returns = []
    annual_excess_returns = []
    holding_periods = []
    
    with connect_db() as conn:
        for rebalance_date in sorted(portfolios.keys()):
            # 評価日を計算（リバランス日 + horizon_months）
            rebalance_dt = dt.strptime(rebalance_date, "%Y-%m-%d")
            evaluation_dt = rebalance_dt + relativedelta(months=horizon_months)
            evaluation_date = evaluation_dt.strftime("%Y-%m-%d")
            
            # データの終端を超える場合は除外
            if evaluation_date > latest_date:
                print(f"  除外: {rebalance_date}（評価日{evaluation_date}がデータ終端{latest_date}を超える）")
                continue
            
            # ポートフォリオをDBに一時保存
            portfolio_df = portfolios[rebalance_date]
            save_portfolio(conn, portfolio_df)
            conn.commit()
            
            # パフォーマンスを計算（固定ホライズン）
            perf = calculate_portfolio_performance(
                rebalance_date=rebalance_date,
                as_of_date=evaluation_date,
                portfolio_table="portfolio_monthly",
            )
            
            # 一時的に保存したポートフォリオを削除
            conn.execute(
                "DELETE FROM portfolio_monthly WHERE rebalance_date = ?",
                (rebalance_date,)
            )
            conn.commit()
            
            if "error" not in perf:
                total_return_pct = perf.get("total_return_pct")
                topix_comparison = perf.get("topix_comparison", {})
                excess_return_pct = topix_comparison.get("excess_return_pct")
                
                # 保有期間を計算（固定ホライズン）
                holding_years = horizon_months / 12.0
                
                # 年率化
                if total_return_pct is not None and not pd.isna(total_return_pct):
                    return_factor = 1 + total_return_pct / 100
                    if return_factor > 0:
                        annual_return = return_factor ** (1 / holding_years) - 1
                        annual_return_pct = annual_return * 100
                        if not isinstance(annual_return_pct, complex):
                            annual_returns.append(annual_return_pct)
                            holding_periods.append(holding_years)
                
                if excess_return_pct is not None and not pd.isna(excess_return_pct):
                    excess_factor = 1 + excess_return_pct / 100
                    if excess_factor > 0:
                        annual_excess_return = excess_factor ** (1 / holding_years) - 1
                        annual_excess_return_pct = annual_excess_return * 100
                        if not isinstance(annual_excess_return_pct, complex):
                            annual_excess_returns.append(annual_excess_return_pct)
                
                performances.append(perf)
    
    if not performances:
        raise RuntimeError("No performances were calculated")
    
    # 集計指標を計算
    mean_annual_excess_return = np.mean(annual_excess_returns) if annual_excess_returns else 0.0
    median_annual_excess_return = np.median(annual_excess_returns) if annual_excess_returns else 0.0
    mean_annual_return = np.mean(annual_returns) if annual_returns else 0.0
    median_annual_return = np.median(annual_returns) if annual_returns else 0.0
    
    # 勝率
    win_rate = sum(1 for r in annual_excess_returns if r > 0) / len(annual_excess_returns) if annual_excess_returns else 0.0
    
    result = {
        "mean_annual_excess_return_pct": mean_annual_excess_return,
        "median_annual_excess_return_pct": median_annual_excess_return,
        "mean_annual_return_pct": mean_annual_return,
        "median_annual_return_pct": median_annual_return,
        "win_rate": win_rate,
        "num_portfolios": len(performances),
        "mean_holding_years": np.mean(holding_periods) if holding_periods else 0.0,
        "horizon_months": horizon_months,
        "last_date": latest_date,
    }
    
    return result


def test_seed_robustness_fixed_horizon(
    json_file: str,
    start_date: str,
    end_date: str,
    horizon_months: int,
    n_seeds: int = 20,
    train_ratio: float = 0.8,
    cost_bps: float = 0.0,
    cache_dir: str = "cache/features",
    n_jobs: int = -1,
) -> Dict[str, Any]:
    """
    固定ホライズン版 seed耐性テストを実行
    
    Args:
        json_file: 最良パラメータを含むJSONファイル
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        horizon_months: ホライズン（月数、例：12, 24, 36）
        n_seeds: テストするseedの数
        train_ratio: 学習データの割合
        cost_bps: 取引コスト（bps）
        cache_dir: キャッシュディレクトリ
    
    Returns:
        テスト結果の辞書
    """
    print("=" * 80)
    print(f"固定ホライズン版 seed耐性テスト（{horizon_months}M）")
    print("=" * 80)
    print(f"JSONファイル: {json_file}")
    print(f"期間: {start_date} ～ {end_date}")
    print(f"ホライズン: {horizon_months}ヶ月")
    print(f"テストseed数: {n_seeds}")
    print(f"学習/テスト分割: {train_ratio:.1%} / {1-train_ratio:.1%}")
    print()
    
    # 最良パラメータを読み込む
    print("最良パラメータを読み込みます...")
    best_params = load_best_params(json_file)
    strategy_params, entry_params = build_params_from_json(best_params)
    print("✓ パラメータ読み込み完了")
    print()
    
    # リバランス日を取得
    print("リバランス日を取得します...")
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"✓ リバランス日数: {len(rebalance_dates)}")
    print()
    
    # 特徴量キャッシュを構築
    print("特徴量キャッシュを構築します...")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    features_dict, prices_dict = feature_cache.warm(
        rebalance_dates,
        n_jobs=-1
    )
    print(f"✓ 特徴量: {len(features_dict)}日分、価格データ: {len(prices_dict)}日分")
    print()
    
    # 各seedでテスト（並列化対応）
    print("=" * 80)
    print("各seedでテストデータのパフォーマンスを計算します...")
    print("=" * 80)
    
    # 並列化実行
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import multiprocessing as mp
    from dataclasses import fields
    
    # 並列数（デフォルト: CPU数、SQLite環境では制限）
    if n_jobs == -1:
        n_jobs = min(mp.cpu_count(), 4)  # SQLite環境では4並列まで推奨
    else:
        n_jobs = min(n_jobs, mp.cpu_count())
    
    # dataclassを辞書に変換（pickle可能にするため）
    strategy_params_dict = {
        field.name: getattr(strategy_params, field.name)
        for field in fields(StrategyParams)
    }
    entry_params_dict = {
        field.name: getattr(entry_params, field.name)
        for field in fields(EntryScoreParams)
    }
    
    test_results = []
    seed_details = []
    
    print(f"並列実行: {n_jobs}プロセス")
    
    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        # 全seedのタスクを投入
        future_to_seed = {
            executor.submit(
                _process_single_seed_wrapper,
                seed,
                rebalance_dates,
                train_ratio,
                horizon_months,
                cost_bps,
                strategy_params_dict,
                entry_params_dict,
                features_dict,
                prices_dict,
            ): seed
            for seed in range(1, n_seeds + 1)
        }
        
        # 完了したタスクから順に処理
        for future in as_completed(future_to_seed):
            seed, test_mean_excess_ann, seed_detail = future.result()
            
            if test_mean_excess_ann is not None and seed_detail is not None:
                test_results.append(test_mean_excess_ann)
                seed_details.append(seed_detail)
                
                print(f"\n[Seed {seed}/{n_seeds}]")
                print(f"  学習データ: {len(seed_detail['train_dates'])}日, テストデータ: {len(seed_detail['test_dates'])}日")
                print(f"  テストデータ年率超過リターン（平均）: {test_mean_excess_ann:.4f}%")
                print(f"  評価対象ポートフォリオ数: {seed_detail.get('test_num_portfolios', 0)}")
    
    if not test_results:
        raise RuntimeError("No test results were calculated")
    
    # 統計を計算
    test_results_array = np.array(test_results)
    
    mean_val = np.mean(test_results_array)
    median_val = np.median(test_results_array)
    std_val = np.std(test_results_array)
    min_val = np.min(test_results_array)
    max_val = np.max(test_results_array)
    
    percentile_10 = np.percentile(test_results_array, 10)
    percentile_25 = np.percentile(test_results_array, 25)
    percentile_75 = np.percentile(test_results_array, 75)
    percentile_90 = np.percentile(test_results_array, 90)
    
    positive_ratio = np.sum(test_results_array > 0) / len(test_results_array)
    
    # 結果を表示
    print()
    print("=" * 80)
    print(f"【固定ホライズン{horizon_months}M seed耐性テスト結果】")
    print("=" * 80)
    print(f"テストseed数: {n_seeds}")
    print(f"最良パラメータ（固定）: {json_file}")
    print()
    print("テストデータ年率超過リターン（平均）の分布:")
    print(f"  平均: {mean_val:.4f}%")
    print(f"  中央値: {median_val:.4f}%")
    print(f"  標準偏差: {std_val:.4f}%")
    print(f"  最小値: {min_val:.4f}%")
    print(f"  最大値: {max_val:.4f}%")
    print()
    print("パーセンタイル:")
    print(f"  下位10%: {percentile_10:.4f}%")
    print(f"  下位25%: {percentile_25:.4f}%")
    print(f"  上位25%: {percentile_75:.4f}%")
    print(f"  上位10%: {percentile_90:.4f}%")
    print()
    print(f"正の値の割合: {positive_ratio:.1%} ({np.sum(test_results_array > 0)}/{n_seeds})")
    print()
    
    # 合格判定（事前に固定）
    print("【合格判定】")
    if horizon_months == 12:
        # 12M: 中央値 > 0、正の割合 ≥ 60%
        passed = bool(median_val > 0 and positive_ratio >= 0.60)
        criteria = "中央値 > 0 かつ 正の割合 ≥ 60%"
    elif horizon_months == 24:
        # 24M: 中央値 > 0（正の割合は参考）
        passed = bool(median_val > 0)
        criteria = "中央値 > 0"
    else:  # 36M
        # 36M: 中央値が0付近でも「極端に悪くない」こと（p10が大崩れしない等）
        passed = bool(percentile_10 > -2.0)  # p10が-2%以上
        criteria = "下位10% > -2.0%"
    
    if passed:
        print(f"✅ 合格: {criteria}を満たしています")
    else:
        print(f"❌ 不合格: {criteria}を満たしていません")
    print()
    
    # 結果を辞書にまとめる（JSONシリアライズ可能な型に変換）
    result = {
        "json_file": json_file,
        "start_date": start_date,
        "end_date": end_date,
        "horizon_months": int(horizon_months),
        "n_seeds": int(n_seeds),
        "train_ratio": float(train_ratio),
        "test_results": [float(x) for x in test_results],
        "statistics": {
            "mean": float(mean_val),
            "median": float(median_val),
            "std": float(std_val),
            "min": float(min_val),
            "max": float(max_val),
            "percentile_10": float(percentile_10),
            "percentile_25": float(percentile_25),
            "percentile_75": float(percentile_75),
            "percentile_90": float(percentile_90),
            "positive_ratio": float(positive_ratio),
        },
        "seed_details": [
            {
                "seed": int(detail["seed"]),
                "train_dates": detail["train_dates"],
                "test_dates": detail["test_dates"],
                "test_mean_annual_excess_return_pct": float(detail["test_mean_annual_excess_return_pct"]) if detail["test_mean_annual_excess_return_pct"] is not None else None,
                "test_median_annual_excess_return_pct": float(detail["test_median_annual_excess_return_pct"]) if detail["test_median_annual_excess_return_pct"] is not None else None,
                "test_mean_annual_return_pct": float(detail["test_mean_annual_return_pct"]) if detail["test_mean_annual_return_pct"] is not None else None,
                "test_win_rate": float(detail["test_win_rate"]) if detail["test_win_rate"] is not None else None,
                "test_num_portfolios": int(detail["test_num_portfolios"]) if detail["test_num_portfolios"] is not None else None,
            }
            for detail in seed_details
        ],
        "passed": bool(passed),
        "criteria": str(criteria),
    }
    
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="固定ホライズン版 seed耐性テスト"
    )
    parser.add_argument(
        "--json-file",
        type=str,
        required=True,
        help="最良パラメータを含むJSONファイル",
    )
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="開始日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="終了日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        required=True,
        choices=[12, 24, 36],
        help="ホライズン（月数: 12, 24, 36）",
    )
    parser.add_argument(
        "--n-seeds",
        type=int,
        default=20,
        help="テストするseedの数（デフォルト: 20）",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="学習データの割合（デフォルト: 0.8）",
    )
    parser.add_argument(
        "--cost-bps",
        type=float,
        default=0.0,
        help="取引コスト（bps、デフォルト: 0.0）",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default="cache/features",
        help="キャッシュディレクトリ（デフォルト: cache/features）",
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=-1,
        help="並列数（-1で自動、デフォルト: -1）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="結果をJSONファイルに保存（Noneの場合は自動生成）",
    )
    
    args = parser.parse_args()
    
    result = test_seed_robustness_fixed_horizon(
        json_file=args.json_file,
        start_date=args.start,
        end_date=args.end,
        horizon_months=args.horizon,
        n_seeds=args.n_seeds,
        train_ratio=args.train_ratio,
        cost_bps=args.cost_bps,
        cache_dir=args.cache_dir,
        n_jobs=args.n_jobs,
    )
    
    # 結果をJSONファイルに保存
    if args.output is None:
        output_file = f"seed_robustness_fixed_horizon_{args.horizon}M.json"
    else:
        output_file = args.output
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"結果を保存しました: {output_file}")

