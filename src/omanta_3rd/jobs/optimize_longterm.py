"""長期保有型のパラメータ最適化システム

リバランス日基準でランダムに学習/テストデータを分割し、過学習を抑制します。
長期保有型なので、月次リバランス型の標準的な評価指標（Sharpe ratio等）は計算しません。

設計:
- リバランス日をランダムに学習/テストに分割（デフォルト: 80/20）
- 学習データで最適化、テストデータで評価
- 評価指標: 累積リターン、年率リターン、最大ドローダウン等
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import random
from dataclasses import dataclass, replace, fields
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Literal
import numpy as np
import pandas as pd
import optuna
from optuna.visualization import plot_optimization_history, plot_param_importances

from ..infra.db import connect_db
from ..jobs.monthly_run import (
    StrategyParams,
    build_features,
    select_portfolio,
    save_features,
    save_portfolio,
)
from ..jobs.batch_monthly_run import get_monthly_rebalance_dates
from ..backtest.feature_cache import FeatureCache
from ..backtest.performance import calculate_portfolio_performance
from ..jobs.optimize import (
    EntryScoreParams,
    _entry_score_with_params,
    _calculate_entry_score_with_params,
    _select_portfolio_with_params,
)

# optimize_timeseries.pyから必要な関数をインポート
from .optimize_timeseries import (
    _run_single_backtest_portfolio_only,
    _setup_blas_threads,
)


def split_rebalance_dates(
    rebalance_dates: List[str],
    train_ratio: float = 0.8,
    random_seed: Optional[int] = 42,
) -> Tuple[List[str], List[str]]:
    """
    リバランス日をランダムに学習/テストに分割
    
    Args:
        rebalance_dates: リバランス日のリスト
        train_ratio: 学習データの割合（デフォルト: 0.8、0.0 < train_ratio < 1.0）
        random_seed: ランダムシード（Noneの場合は非再現、デフォルト: 42で再現可能）
    
    Returns:
        (train_dates, test_dates) のタプル
    
    Raises:
        ValueError: train_ratioが範囲外、またはrebalance_datesが2未満の場合
    """
    # バリデーション
    if not 0.0 < train_ratio < 1.0:
        raise ValueError(f"train_ratio must be in (0, 1), got {train_ratio}")
    if len(rebalance_dates) < 2:
        raise ValueError(f"rebalance_dates must have at least 2 dates, got {len(rebalance_dates)}")
    
    # 重複を除去（念のため）
    unique_dates = list(dict.fromkeys(rebalance_dates))  # 順序を保持しつつ重複除去
    if len(unique_dates) < 2:
        raise ValueError(f"After removing duplicates, rebalance_dates must have at least 2 dates, got {len(unique_dates)}")
    
    shuffled = unique_dates.copy()
    
    # 副作用のないローカルRNGを使用（グローバル乱数状態を汚さない）
    if random_seed is not None:
        rng = random.Random(random_seed)
    else:
        rng = random.Random()  # OS乱数を使用（非再現）
    rng.shuffle(shuffled)
    
    # 学習/テストに分割（roundを使用して80/20に近づける）
    # ただし、train/test両方が最低1つになるようにクリップ
    n_train = int(round(len(shuffled) * train_ratio))
    n_train = max(1, min(len(shuffled) - 1, n_train))  # 1 <= n_train <= len-1
    
    train_dates = sorted(shuffled[:n_train])
    test_dates = sorted(shuffled[n_train:])
    
    return train_dates, test_dates


def calculate_longterm_performance(
    rebalance_dates: List[str],
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
    cost_bps: float = 0.0,
    n_jobs: int = -1,
    features_dict: Optional[Dict[str, pd.DataFrame]] = None,
    prices_dict: Optional[Dict[str, Dict[str, List[float]]]] = None,
) -> Dict[str, Any]:
    """
    長期保有型のパフォーマンスを計算
    
    Args:
        rebalance_dates: リバランス日のリスト
        strategy_params: StrategyParams
        entry_params: EntryScoreParams
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        n_jobs: 並列実行数（-1でCPU数）
        features_dict: 特徴量辞書（{rebalance_date: features_df}）
        prices_dict: 価格データ辞書（{rebalance_date: {code: [adj_close, ...]}}）
    
    Returns:
        パフォーマンス指標の辞書
    """
    print(f"      [calculate_longterm_performance] 関数開始 (rebalance_dates数: {len(rebalance_dates)})")
    import sys
    sys.stdout.flush()
    
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor, as_completed
    
    # 並列実行数の決定
    if n_jobs == -1:
        n_jobs = min(len(rebalance_dates), mp.cpu_count())
    elif n_jobs <= 0:
        n_jobs = 1
    
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
    
    print(f"      [calculate_longterm_performance] ポートフォリオ選定開始 (n_jobs={n_jobs}, リバランス日数={len(rebalance_dates)})")
    sys.stdout.flush()
    
    # 並列実行: ポートフォリオ選定のみ
    if n_jobs > 1 and len(rebalance_dates) > 1:
        print(f"      [calculate_longterm_performance] 並列実行モード (max_workers={n_jobs})")
        sys.stdout.flush()
        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            futures = {
                executor.submit(
                    _run_single_backtest_portfolio_only,
                    rebalance_date,
                    strategy_params_dict,
                    entry_params_dict,
                    features_dict.get(rebalance_date) if features_dict else None,
                    prices_dict.get(rebalance_date) if prices_dict else None,
                ): rebalance_date
                for rebalance_date in rebalance_dates
            }
            
            for future in as_completed(futures):
                rebalance_date = futures[future]
                try:
                    portfolio = future.result()
                    if portfolio is not None and not portfolio.empty:
                        portfolios[rebalance_date] = portfolio
                except Exception as e:
                    print(f"エラー ({rebalance_date}): {e}")
    else:
        # 逐次実行
        print(f"      [calculate_longterm_performance] 逐次実行モード")
        sys.stdout.flush()
        for i, rebalance_date in enumerate(rebalance_dates, 1):
            print(f"      [calculate_longterm_performance] 処理中 ({i}/{len(rebalance_dates)}): {rebalance_date}")
            sys.stdout.flush()
            portfolio = _run_single_backtest_portfolio_only(
                rebalance_date,
                strategy_params_dict,
                entry_params_dict,
                features_dict.get(rebalance_date) if features_dict else None,
                prices_dict.get(rebalance_date) if prices_dict else None,
            )
            if portfolio is not None and not portfolio.empty:
                portfolios[rebalance_date] = portfolio
                print(f"      [calculate_longterm_performance] ✓ {rebalance_date}完了 (銘柄数: {len(portfolio)})")
            else:
                print(f"      [calculate_longterm_performance] ⚠️  {rebalance_date}は空ポートフォリオ")
            sys.stdout.flush()
    
    if not portfolios:
        raise RuntimeError("No portfolios were generated")
    
    print(f"      [calculate_longterm_performance] ポートフォリオ選定完了: {len(portfolios)}個")
    sys.stdout.flush()
    
    # 各ポートフォリオのパフォーマンスを計算
    # 注意: 最適化中はDBに保存せず、ポートフォリオDataFrameから直接計算
    print(f"      [calculate_longterm_performance] パフォーマンス計算開始...")
    sys.stdout.flush()
    performances = []
    with connect_db() as conn:
        # 最新の評価日を取得
        latest_date_df = pd.read_sql_query(
            "SELECT MAX(date) as max_date FROM prices_daily",
            conn
        )
        latest_date = latest_date_df["max_date"].iloc[0] if not latest_date_df.empty else None
        
        if latest_date is None:
            raise RuntimeError("No price data available")
        
        for rebalance_date in sorted(portfolios.keys()):
            # ポートフォリオをDBに一時保存（calculate_portfolio_performanceがDBから読み込むため）
            portfolio_df = portfolios[rebalance_date]
            
            # デバッグ: ポートフォリオの銘柄数を確認
            if len(portfolio_df) == 0:
                print(f"警告: {rebalance_date}のポートフォリオが空です")
                continue
            
            save_portfolio(conn, portfolio_df)
            # 重要: 別の接続から読み込む前にコミットが必要
            conn.commit()
            
            # パフォーマンスを計算
            perf = calculate_portfolio_performance(rebalance_date, latest_date)
            if "error" not in perf:
                performances.append(perf)
            else:
                # エラーが発生した場合は警告を出力
                print(f"警告: {rebalance_date}のパフォーマンス計算でエラーが発生しました: {perf.get('error', 'Unknown error')}")
            
            # 最適化中は一時的なポートフォリオなので削除（クリーンアップ）
            # 注意: 本番運用時は削除しない
            conn.execute(
                "DELETE FROM portfolio_monthly WHERE rebalance_date = ?",
                (rebalance_date,)
            )
            conn.commit()
    
    if not performances:
        raise RuntimeError("No performances were calculated")
    
    # 集計指標を計算
    # 改善: 各ポートフォリオをその保有期間で個別に年率化してから集計
    from datetime import datetime as dt
    
    annual_returns = []  # 各ポートフォリオの年率リターン
    annual_excess_returns = []  # 各ポートフォリオの年率超過リターン（目的関数用）
    total_returns = []  # 累積リターン（参考用）
    excess_returns = []  # 累積超過リターン（参考用）
    holding_periods = []  # 保有期間（年）
    
    for perf in performances:
        rebalance_date = perf.get("rebalance_date")
        total_return_pct = perf.get("total_return_pct")
        # excess_return_pctはtopix_comparisonの中にある
        topix_comparison = perf.get("topix_comparison", {})
        excess_return_pct = topix_comparison.get("excess_return_pct")
        
        # total_return_pctがNoneまたはNaNの場合はスキップ（品質が低いポートフォリオ）
        if rebalance_date and total_return_pct is not None and not pd.isna(total_return_pct):
            # 保有期間を計算
            rebalance_dt = dt.strptime(rebalance_date, "%Y-%m-%d")
            latest_dt = dt.strptime(latest_date, "%Y-%m-%d")
            holding_years = (latest_dt - rebalance_dt).days / 365.25
            
            # 累積リターンが-100%未満の場合は年率化をスキップ（年率化で複素数が生成される）
            return_factor = 1 + total_return_pct / 100
            if return_factor <= 0:
                print(f"警告: {rebalance_date}の累積リターンが-100%未満のため、年率化をスキップします。累積リターン: {total_return_pct:.2f}%")
                # 累積値は参考用に記録（年率化はスキップ）
                total_returns.append(total_return_pct)
                if excess_return_pct is not None and not pd.isna(excess_return_pct):
                    excess_returns.append(excess_return_pct)
                continue
            
            # 各ポートフォリオをその保有期間で個別に年率化
            if holding_years > 0:
                annual_return = return_factor ** (1 / holding_years) - 1
                annual_return_pct = annual_return * 100
                # 複素数チェック（念のため）
                if isinstance(annual_return_pct, complex):
                    # 複素数の場合はスキップ
                    print(f"警告: {rebalance_date}の年率リターンが複素数になりました。累積リターン: {total_return_pct:.2f}%, 保有期間: {holding_years:.2f}年")
                    total_returns.append(total_return_pct)
                    if excess_return_pct is not None and not pd.isna(excess_return_pct):
                        excess_returns.append(excess_return_pct)
                    continue
                annual_returns.append(annual_return_pct)
                holding_periods.append(holding_years)
                
                # 超過リターンも年率化（目的関数用）
                if excess_return_pct is not None and not pd.isna(excess_return_pct):
                    # 超過リターンを年率化: (1 + excess_return_pct / 100) ** (1 / holding_years) - 1
                    # 注意: 累積超過リターンが-100%未満の場合（1 + excess_return_pct/100 < 0）、
                    #       年率化で複素数が生成される可能性があるため、スキップする
                    excess_factor = 1 + excess_return_pct / 100
                    if excess_factor > 0:
                        annual_excess_return = excess_factor ** (1 / holding_years) - 1
                        annual_excess_return_pct = annual_excess_return * 100
                        # 複素数チェック（念のため）
                        if isinstance(annual_excess_return_pct, complex):
                            # 複素数の場合はスキップ
                            print(f"警告: {rebalance_date}の年率超過リターンが複素数になりました。累積超過リターン: {excess_return_pct:.2f}%, 保有期間: {holding_years:.2f}年")
                        else:
                            annual_excess_returns.append(annual_excess_return_pct)
                    else:
                        # 累積超過リターンが-100%未満の場合はスキップ（年率化不可）
                        print(f"警告: {rebalance_date}の累積超過リターンが-100%未満のため、年率化をスキップします。累積超過リターン: {excess_return_pct:.2f}%")
            
            total_returns.append(total_return_pct)
            # excess_return_pctもNone/NaNチェック（累積値、参考用）
            if excess_return_pct is not None and not pd.isna(excess_return_pct):
                excess_returns.append(excess_return_pct)
    
    # 集計指標を計算
    # 目的関数: 各ポートフォリオの年率超過リターンの平均（TOPIXに対する超過リターン）
    mean_annual_excess_return = np.mean(annual_excess_returns) if annual_excess_returns else 0.0
    median_annual_excess_return = np.median(annual_excess_returns) if annual_excess_returns else 0.0
    
    # 参考指標: 年率リターンの平均（TOPIX比較なし）
    mean_annual_return = np.mean(annual_returns) if annual_returns else 0.0
    median_annual_return = np.median(annual_returns) if annual_returns else 0.0
    
    # 参考指標: 累積リターンの平均（従来の方法）
    cumulative_return = np.mean(total_returns) if total_returns else 0.0
    
    # 全体期間での年率化（従来の方法、参考用）
    first_rebalance = min(portfolios.keys())
    start_dt = dt.strptime(first_rebalance, "%Y-%m-%d")
    end_dt = dt.strptime(latest_date, "%Y-%m-%d")
    total_years = (end_dt - start_dt).days / 365.25
    if total_years > 0:
        overall_annual_return = (1 + cumulative_return / 100) ** (1 / total_years) - 1
        overall_annual_return_pct = overall_annual_return * 100
    else:
        overall_annual_return_pct = 0.0
    
    # 平均超過リターン（累積値、参考用）
    mean_excess_return = np.mean(excess_returns) if excess_returns else 0.0
    
    # 勝率（年率超過リターンが正のポートフォリオの割合）
    win_rate = sum(1 for r in annual_excess_returns if r > 0) / len(annual_excess_returns) if annual_excess_returns else 0.0
    
    # 平均保有期間
    mean_holding_years = np.mean(holding_periods) if holding_periods else 0.0
    
    result = {
        # 目的関数用（TOPIXに対する年率超過リターン）
        "mean_annual_excess_return_pct": mean_annual_excess_return,  # 各ポートフォリオの年率超過リターンの平均
        "median_annual_excess_return_pct": median_annual_excess_return,  # 中央値
        # 参考指標: 年率リターン（TOPIX比較なし）
        "mean_annual_return_pct": mean_annual_return,  # 各ポートフォリオの年率リターンの平均
        "median_annual_return_pct": median_annual_return,  # 中央値
        # 参考指標（従来の方法）
        "cumulative_return_pct": cumulative_return,
        "overall_annual_return_pct": overall_annual_return_pct,  # 全体期間での年率化（参考用）
        # その他の指標
        "mean_excess_return_pct": mean_excess_return,  # 累積超過リターン（参考用）
        "win_rate": win_rate,
        "num_portfolios": len(portfolios),
        "num_performances": len(performances),
        "mean_holding_years": mean_holding_years,
        "total_years": total_years,
        "first_rebalance": first_rebalance,
        "last_date": latest_date,
    }
    
    return result


def objective_longterm(
    trial: optuna.Trial,
    train_dates: List[str],
    study_type: Literal["A", "B", "C"],
    cost_bps: float = 0.0,
    n_jobs: int = -1,
    features_dict: Optional[Dict[str, pd.DataFrame]] = None,
    prices_dict: Optional[Dict[str, Dict[str, List[float]]]] = None,
) -> float:
    """
    Optunaの目的関数（長期保有型）
    
    Args:
        trial: OptunaのTrialオブジェクト
        train_dates: 学習用リバランス日のリスト
        study_type: "A"（BB寄り・低ROE閾値）、"B"（Value寄り・ROE閾値やや高め）、
                    "C"（Study A/B統合・広範囲探索）
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        n_jobs: 並列実行数（-1でCPU数）
        features_dict: 特徴量辞書（事前計算済み）
        prices_dict: 価格データ辞書（事前計算済み）
    
    Returns:
        最適化対象の値（年率超過リターン、TOPIXに対する超過リターン）
    """
    print(f"    [objective_longterm] 関数開始 (Trial {trial.number})")
    import sys
    sys.stdout.flush()
    
    # StrategyParamsのパラメータ
    # 月次リバランスの最適化結果を参考にせず、広い範囲で探索
    print(f"    [objective_longterm] パラメータ提案開始...")
    sys.stdout.flush()
    w_quality = trial.suggest_float("w_quality", 0.05, 0.50)
    print(f"    [objective_longterm] w_quality取得完了: {w_quality}")
    sys.stdout.flush()
    w_growth = trial.suggest_float("w_growth", 0.01, 0.30)
    w_record_high = trial.suggest_float("w_record_high", 0.01, 0.20)
    w_size = trial.suggest_float("w_size", 0.05, 0.40)
    
    # Study A/B/Cで異なる範囲
    if study_type == "A":
        # Study A: BB寄り・低ROE閾値
        w_value = trial.suggest_float("w_value", 0.10, 0.50)
        w_forward_per = trial.suggest_float("w_forward_per", 0.20, 0.90)
        roe_min = trial.suggest_float("roe_min", 0.00, 0.12)
        bb_weight = trial.suggest_float("bb_weight", 0.30, 0.95)
    elif study_type == "B":
        # Study B: Value寄り・ROE閾値やや高め（ただし、より広い範囲で探索）
        w_value = trial.suggest_float("w_value", 0.20, 0.60)
        w_forward_per = trial.suggest_float("w_forward_per", 0.20, 0.80)
        roe_min = trial.suggest_float("roe_min", 0.00, 0.20)
        bb_weight = trial.suggest_float("bb_weight", 0.20, 0.80)
    else:  # study_type == "C"
        # Study C: Study A/B統合・広範囲探索
        # Study A: w_value(0.10-0.50), Study B: w_value(0.20-0.60) → 統合: 0.10-0.60
        w_value = trial.suggest_float("w_value", 0.10, 0.60)
        # Study A: w_forward_per(0.20-0.90), Study B: w_forward_per(0.20-0.80) → 統合: 0.20-0.90
        w_forward_per = trial.suggest_float("w_forward_per", 0.20, 0.90)
        # Study A: roe_min(0.00-0.12), Study B: roe_min(0.00-0.20) → 統合: 0.00-0.20
        roe_min = trial.suggest_float("roe_min", 0.00, 0.20)
        # Study A: bb_weight(0.30-0.95), Study B: bb_weight(0.20-0.80) → 統合: 0.20-0.95
        bb_weight = trial.suggest_float("bb_weight", 0.20, 0.95)
    
    # 正規化（合計が1になるように）
    total = w_quality + w_value + w_growth + w_record_high + w_size
    w_quality /= total
    w_value /= total
    w_growth /= total
    w_record_high /= total
    w_size /= total
    
    w_pbr = 1.0 - w_forward_per
    
    # 共通パラメータ（Study A/B共通、以前と同じ範囲に固定、比較の公平性のため）
    liquidity_quantile_cut = trial.suggest_float("liquidity_quantile_cut", 0.10, 0.30)
    
    # RSIパラメータ（順張り/逆張りを対称に探索）
    RSI_LOW, RSI_HIGH = 15.0, 85.0
    rsi_min_width = 20.0  # 最小幅制約（固定値、探索してもOK）
    
    # 最初にOptunaでサンプリング
    rsi_base = trial.suggest_float("rsi_base", RSI_LOW, RSI_HIGH)
    rsi_max = trial.suggest_float("rsi_max", RSI_LOW, RSI_HIGH)
    
    # 最小幅制約を満たすまで再サンプリング（trialのシードに基づいて再現可能に）
    max_retries = 100  # 最大再試行回数（無限ループ防止）
    retry_count = 0
    
    # trialのシードに基づいた再現可能な乱数生成器を作成
    # trial.numberとtrial._trial_idを使ってシードを生成
    trial_seed = hash((trial.number, getattr(trial, '_trial_id', trial.number))) % (2**31)
    rng = np.random.RandomState(trial_seed)
    
    while abs(rsi_max - rsi_base) < rsi_min_width and retry_count < max_retries:
        rsi_base = rng.uniform(RSI_LOW, RSI_HIGH)
        rsi_max = rng.uniform(RSI_LOW, RSI_HIGH)
        retry_count += 1
    
    if retry_count > 0:
        # 再サンプリングした場合は記録
        trial.set_user_attr("rsi_resampled", True)
        trial.set_user_attr("rsi_retry_count", retry_count)
    
    # 最終的なパラメータを記録
    trial.set_user_attr("rsi_base_final", rsi_base)
    trial.set_user_attr("rsi_max_final", rsi_max)
    
    # BB Z-scoreパラメータ（順張り/逆張りを対称に探索）
    BB_LOW, BB_HIGH = -3.5, 3.5
    bb_z_min_width = 1.0  # 最小幅制約（固定値、探索してもOK）
    
    # 最初にOptunaでサンプリング
    bb_z_base = trial.suggest_float("bb_z_base", BB_LOW, BB_HIGH)
    bb_z_max = trial.suggest_float("bb_z_max", BB_LOW, BB_HIGH)
    
    # 最小幅制約を満たすまで再サンプリング（trialのシードに基づいて再現可能に）
    # RSIとは別のシード系列を使用（オフセットを追加）
    bb_trial_seed = (trial_seed + 10000) % (2**31)
    bb_rng = np.random.RandomState(bb_trial_seed)
    
    retry_count = 0
    while abs(bb_z_max - bb_z_base) < bb_z_min_width and retry_count < max_retries:
        bb_z_base = bb_rng.uniform(BB_LOW, BB_HIGH)
        bb_z_max = bb_rng.uniform(BB_LOW, BB_HIGH)
        retry_count += 1
    
    if retry_count > 0:
        # 再サンプリングした場合は記録
        trial.set_user_attr("bb_resampled", True)
        trial.set_user_attr("bb_retry_count", retry_count)
    
    # 最終的なパラメータを記録
    trial.set_user_attr("bb_z_base_final", bb_z_base)
    trial.set_user_attr("bb_z_max_final", bb_z_max)
    
    rsi_weight = 1.0 - bb_weight
    
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
        w_forward_per=w_forward_per,
        w_pbr=w_pbr,
        roe_min=roe_min,
        liquidity_quantile_cut=liquidity_quantile_cut,
    )
    
    # EntryScoreParamsを構築
    entry_params = EntryScoreParams(
        rsi_base=rsi_base,
        rsi_max=rsi_max,
        bb_z_base=bb_z_base,
        bb_z_max=bb_z_max,
        bb_weight=bb_weight,
        rsi_weight=rsi_weight,
        rsi_min_width=rsi_min_width,
        bb_z_min_width=bb_z_min_width,
    )
    
    # 順張り/逆張りの方向と幅をログに記録
    rsi_direction = "順張り" if rsi_max > rsi_base else "逆張り"
    bb_direction = "順張り" if bb_z_max > bb_z_base else "逆張り"
    trial.set_user_attr("rsi_direction", rsi_direction)
    trial.set_user_attr("bb_direction", bb_direction)
    trial.set_user_attr("rsi_width", abs(rsi_max - rsi_base))
    trial.set_user_attr("bb_z_width", abs(bb_z_max - bb_z_base))
    
    # バックテスト実行（長期保有型）
    print(f"    [objective_longterm] calculate_longterm_performance呼び出し...")
    import sys
    sys.stdout.flush()
    perf = calculate_longterm_performance(
        train_dates,
        strategy_params,
        entry_params,
        cost_bps=cost_bps,
        n_jobs=n_jobs,
        features_dict=features_dict,
        prices_dict=prices_dict,
    )
    print(f"    [objective_longterm] calculate_longterm_performance完了")
    sys.stdout.flush()
    
    # 目的関数: 各ポートフォリオの年率超過リターンの平均（TOPIXに対する超過リターン）
    objective_value = perf["mean_annual_excess_return_pct"]
    
    # デバッグ用ログ出力
    log_msg = (
        f"[Trial {trial.number}] "
        f"objective={objective_value:.4f}%, "
        f"median_excess={perf['median_annual_excess_return_pct']:.4f}%, "
        f"median_return={perf['median_annual_return_pct']:.4f}%, "
        f"cumulative={perf['cumulative_return_pct']:.4f}%, "
        f"excess_cumulative={perf['mean_excess_return_pct']:.4f}%, "
        f"win_rate={perf['win_rate']:.4f}, "
        f"mean_holding={perf['mean_holding_years']:.2f}年"
    )
    print(log_msg)
    
    return objective_value


def main(
    start_date: str,
    end_date: str,
    study_type: Literal["A", "B", "C"],
    n_trials: int = 200,
    study_name: Optional[str] = None,
    n_jobs: int = -1,
    bt_workers: int = -1,
    cost_bps: float = 0.0,
    storage: Optional[str] = None,
    no_db_write: bool = False,
    cache_dir: str = "cache/features",
    train_ratio: float = 0.8,
    random_seed: int = 42,
):
    """
    長期保有型の最適化を実行
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        study_type: "A"（BB寄り・低ROE閾値）または "B"（Value寄り・ROE閾値やや高め）
        n_trials: 試行回数
        study_name: スタディ名（Noneの場合は自動生成）
        n_jobs: trial並列数（-1でCPU数）
        bt_workers: trial内バックテストの並列数
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        storage: Optunaストレージ（Noneの場合はSQLite）
        no_db_write: 最適化中にDBに書き込まない
        cache_dir: キャッシュディレクトリ
        train_ratio: 学習データの割合（デフォルト: 0.8）
        random_seed: ランダムシード（デフォルト: 42）
    """
    # BLASスレッドを1に設定
    _setup_blas_threads()
    
    if study_type == "A":
        study_type_desc = "BB寄り・低ROE閾値"
    elif study_type == "B":
        study_type_desc = "Value寄り・ROE閾値やや高め"
    else:  # study_type == "C"
        study_type_desc = "Study A/B統合・広範囲探索"
    
    print("=" * 80)
    print(f"長期保有型パラメータ最適化システム（Study {study_type}: {study_type_desc}）")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"試行回数: {n_trials}")
    print(f"取引コスト: {cost_bps} bps")
    print(f"学習/テスト分割: {train_ratio:.1%} / {1-train_ratio:.1%}")
    print(f"ランダムシード: {random_seed}")
    print("=" * 80)
    print()
    
    # リバランス日を取得
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"リバランス日数: {len(rebalance_dates)}")
    print(f"最初: {rebalance_dates[0] if rebalance_dates else 'N/A'}")
    print(f"最後: {rebalance_dates[-1] if rebalance_dates else 'N/A'}")
    print()
    
    if not rebalance_dates:
        print("❌ リバランス日が見つかりませんでした")
        return
    
    # 学習/テストに分割
    try:
        train_dates, test_dates = split_rebalance_dates(
            rebalance_dates,
            train_ratio=train_ratio,
            random_seed=random_seed,
        )
    except ValueError as e:
        print(f"❌ データ分割エラー: {e}")
        return
    
    print(f"学習データ: {len(train_dates)}日 ({len(train_dates)/len(rebalance_dates):.1%})")
    print(f"  最初: {train_dates[0] if train_dates else 'N/A'}")
    print(f"  最後: {train_dates[-1] if train_dates else 'N/A'}")
    print(f"テストデータ: {len(test_dates)}日 ({len(test_dates)/len(rebalance_dates):.1%})")
    print(f"  最初: {test_dates[0] if test_dates else 'N/A'}")
    print(f"  最後: {test_dates[-1] if test_dates else 'N/A'}")
    print()
    
    # ログ改善: 年別件数と分布を表示（評価窓の重なりの見える化）
    def get_year_counts(dates: List[str]) -> Dict[int, int]:
        """年別の件数を集計"""
        year_counts = {}
        for date_str in dates:
            year = int(date_str.split("-")[0])
            year_counts[year] = year_counts.get(year, 0) + 1
        return year_counts
    
    train_year_counts = get_year_counts(train_dates)
    test_year_counts = get_year_counts(test_dates)
    
    print("【データ分割の詳細】")
    print("学習データの年別分布:")
    for year in sorted(train_year_counts.keys()):
        print(f"  {year}年: {train_year_counts[year]}日")
    print("テストデータの年別分布:")
    for year in sorted(test_year_counts.keys()):
        print(f"  {year}年: {test_year_counts[year]}日")
    print()
    
    # 特徴量キャッシュを構築（全リバランス日分）
    print("=" * 80)
    print("特徴量キャッシュを構築します...")
    print("=" * 80)
    feature_cache = FeatureCache(cache_dir=cache_dir)
    features_dict, prices_dict = feature_cache.warm(
        rebalance_dates, 
        n_jobs=bt_workers if bt_workers > 0 else -1
    )
    print(f"[FeatureCache] 特徴量: {len(features_dict)}日分、価格データ: {len(prices_dict)}日分")
    print()
    
    # Optunaスタディを作成
    if study_name is None:
        study_name = f"optimization_longterm_study{study_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # ストレージの設定
    if storage is None:
        storage = f"sqlite:///optuna_{study_name}.db"
    
    # Optunaのsamplerにシードを設定（再現性のため）
    sampler = optuna.samplers.TPESampler(seed=random_seed)
    
    study = optuna.create_study(
        direction="maximize",
        study_name=study_name,
        storage=storage,
        load_if_exists=True,
        sampler=sampler,
    )
    
    # 並列化設定
    import multiprocessing as mp
    cpu_count = mp.cpu_count()
    
    if n_jobs == -1:
        if storage.startswith("sqlite"):
            optuna_n_jobs = min(4, max(2, min(4, cpu_count // 8)))
        else:
            optuna_n_jobs = min(8, max(1, cpu_count // 2))
    else:
        optuna_n_jobs = n_jobs
    
    if bt_workers == -1:
        available_cpus = max(1, cpu_count - optuna_n_jobs)
        backtest_n_jobs = max(1, min(len(train_dates), available_cpus))
        if len(train_dates) >= 4 and available_cpus >= 2:
            backtest_n_jobs = max(2, min(len(train_dates), min(4, available_cpus)))
    else:
        backtest_n_jobs = bt_workers
    
    print("最適化を開始します...")
    print(f"CPU数: {cpu_count}")
    print(f"Optuna試行並列数: {optuna_n_jobs}")
    print(f"各試行内のバックテスト並列数: {backtest_n_jobs}")
    print()
    
    # 最適化実行
    study.optimize(
        lambda trial: objective_longterm(
            trial,
            train_dates,
            study_type,
            cost_bps,
            backtest_n_jobs,
            features_dict=features_dict,
            prices_dict=prices_dict,
        ),
        n_trials=n_trials,
        show_progress_bar=True,
        n_jobs=optuna_n_jobs,
    )
    
    # 結果表示
    print()
    print("=" * 80)
    print(f"【最適化結果 - Study {study_type}】")
    print("=" * 80)
    print(f"最良試行: {study.best_trial.number}")
    print(f"最良値（年率超過リターン・平均）: {study.best_value:.4f}%")
    print()
    
    # 順張り/逆張りの方向と幅を表示
    best_trial = study.best_trial
    rsi_direction = best_trial.user_attrs.get("rsi_direction", "不明")
    bb_direction = best_trial.user_attrs.get("bb_direction", "不明")
    rsi_width = best_trial.user_attrs.get("rsi_width", None)
    bb_z_width = best_trial.user_attrs.get("bb_z_width", None)
    print(f"entry_score方向:")
    print(f"  RSI: {rsi_direction} (rsi_base={best_trial.params.get('rsi_base', 'N/A'):.2f}, rsi_max={best_trial.params.get('rsi_max', 'N/A'):.2f}, width={rsi_width:.2f if rsi_width else 'N/A'})")
    print(f"  BB: {bb_direction} (bb_z_base={best_trial.params.get('bb_z_base', 'N/A'):.2f}, bb_z_max={best_trial.params.get('bb_z_max', 'N/A'):.2f}, width={bb_z_width:.2f if bb_z_width else 'N/A'})")
    print()
    
    print("最良パラメータ:")
    for key, value in study.best_params.items():
        print(f"  {key}: {value:.6f}")
    print()
    
    # テストデータで評価
    print("=" * 80)
    print("テストデータで評価します...")
    print("=" * 80)
    
    # 最良パラメータを取得
    best_params = study.best_params
    
    # StrategyParamsを構築
    w_quality = best_params["w_quality"]
    w_value = best_params["w_value"]
    w_growth = best_params["w_growth"]
    w_record_high = best_params["w_record_high"]
    w_size = best_params["w_size"]
    
    # 正規化
    total = w_quality + w_value + w_growth + w_record_high + w_size
    w_quality /= total
    w_value /= total
    w_growth /= total
    w_record_high /= total
    w_size /= total
    
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
        w_forward_per=best_params["w_forward_per"],
        w_pbr=1.0 - best_params["w_forward_per"],
        roe_min=best_params["roe_min"],
        liquidity_quantile_cut=best_params["liquidity_quantile_cut"],
    )
    
    # EntryScoreParamsを構築
    entry_params = EntryScoreParams(
        rsi_base=best_params["rsi_base"],
        rsi_max=best_params["rsi_max"],
        bb_z_base=best_params["bb_z_base"],
        bb_z_max=best_params["bb_z_max"],
        bb_weight=best_params["bb_weight"],
        rsi_weight=1.0 - best_params["bb_weight"],
        rsi_min_width=20.0,  # 最小幅制約（固定値）
        bb_z_min_width=1.0,  # 最小幅制約（固定値）
    )
    
    # テストデータで評価
    test_perf = calculate_longterm_performance(
        test_dates,
        strategy_params,
        entry_params,
        cost_bps=cost_bps,
        n_jobs=backtest_n_jobs,
        features_dict=features_dict,
        prices_dict=prices_dict,
    )
    
    print(f"テストデータ評価結果:")
    print(f"  年率超過リターン（平均）: {test_perf['mean_annual_excess_return_pct']:.4f}%")
    print(f"  年率超過リターン（中央値）: {test_perf['median_annual_excess_return_pct']:.4f}%")
    print(f"  年率リターン（平均）: {test_perf['mean_annual_return_pct']:.4f}%")
    print(f"  年率リターン（中央値）: {test_perf['median_annual_return_pct']:.4f}%")
    print(f"  累積リターン: {test_perf['cumulative_return_pct']:.4f}%")
    print(f"  累積超過リターン: {test_perf['mean_excess_return_pct']:.4f}%")
    print(f"  勝率: {test_perf['win_rate']:.4f}")
    print(f"  ポートフォリオ数: {test_perf['num_portfolios']}")
    print(f"  平均保有期間: {test_perf['mean_holding_years']:.2f}年")
    print()
    
    # ログ改善: 評価窓の重なりの見える化
    print("【評価窓の重なり分析】")
    print("注意: 各ポートフォリオは「リバランス日→最新日」まで評価しているため、")
    print("      異なるリバランス日でも同じ将来期間を共有します。")
    print("      これは「独立性が弱い」評価であることに注意してください。")
    print()
    
    # 共有将来期間の割合を計算（簡易版）
    # テストデータのリバランス日の最小値と最大値を取得
    if test_dates:
        from datetime import datetime as dt
        latest_date = test_perf["last_date"]  # test_perfから取得
        test_min_date = min(test_dates)
        test_max_date = max(test_dates)
        test_min_dt = dt.strptime(test_min_date, "%Y-%m-%d")
        test_max_dt = dt.strptime(test_max_date, "%Y-%m-%d")
        latest_dt = dt.strptime(latest_date, "%Y-%m-%d")
        
        # テストデータの平均保有期間
        test_avg_holding = (latest_dt - test_min_dt).days / 365.25
        
        print(f"テストデータ:")
        print(f"  最初のリバランス日: {test_min_date}")
        print(f"  最後のリバランス日: {test_max_date}")
        print(f"  評価日: {latest_date}")
        print(f"  平均保有期間: {test_avg_holding:.2f}年")
        print(f"  共有将来期間: 全テストポートフォリオが{latest_date}まで評価")
        print()
    
    # 可視化
    try:
        fig1 = plot_optimization_history(study)
        fig1.write_image(f"optimization_history_{study_name}.png")
        print(f"最適化履歴を保存: optimization_history_{study_name}.png")
        
        fig2 = plot_param_importances(study)
        fig2.write_image(f"param_importances_{study_name}.png")
        print(f"パラメータ重要度を保存: param_importances_{study_name}.png")
    except Exception as e:
        print(f"可視化の保存に失敗: {e}")
    
    # 結果をJSONに保存
    result_file = f"optimization_result_{study_name}.json"
    result_data = {
        "study_name": study_name,
        "study_type": study_type,
        "start_date": start_date,
        "end_date": end_date,
        "n_trials": n_trials,
        "train_ratio": train_ratio,
        "random_seed": random_seed,
        "cost_bps": cost_bps,
        "best_trial": {
            "number": study.best_trial.number,
            "value": study.best_value,
            "params": study.best_params,
        },
        "train_performance": {
            "mean_annual_excess_return_pct": study.best_value,
        },
        "test_performance": {
            "mean_annual_excess_return_pct": test_perf["mean_annual_excess_return_pct"],
            "median_annual_excess_return_pct": test_perf["median_annual_excess_return_pct"],
            "mean_annual_return_pct": test_perf["mean_annual_return_pct"],
            "median_annual_return_pct": test_perf["median_annual_return_pct"],
            "cumulative_return_pct": test_perf["cumulative_return_pct"],
            "mean_excess_return_pct": test_perf["mean_excess_return_pct"],
            "win_rate": test_perf["win_rate"],
            "num_portfolios": test_perf["num_portfolios"],
            "mean_holding_years": test_perf["mean_holding_years"],
        },
        "normalized_params": {
            "w_quality": w_quality,
            "w_value": w_value,
            "w_growth": w_growth,
            "w_record_high": w_record_high,
            "w_size": w_size,
            "w_forward_per": best_params["w_forward_per"],
            "w_pbr": 1.0 - best_params["w_forward_per"],
            "roe_min": best_params["roe_min"],
            "liquidity_quantile_cut": best_params["liquidity_quantile_cut"],
            "rsi_base": best_params["rsi_base"],
            "rsi_max": best_params["rsi_max"],
            "bb_z_base": best_params["bb_z_base"],
            "bb_z_max": best_params["bb_z_max"],
            "bb_weight": best_params["bb_weight"],
            "rsi_weight": 1.0 - best_params["bb_weight"],
            "rsi_min_width": 20.0,  # 固定値（最小幅制約）
            "bb_z_min_width": 1.0,  # 固定値（最小幅制約）
        },
    }
    
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)
    print(f"最適化結果を保存: {result_file}")
    print("=" * 80)
    print("最適化が完了しました")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="長期保有型パラメータ最適化システム",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--start", type=str, required=True, help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, required=True, help="終了日（YYYY-MM-DD）")
    parser.add_argument("--study-type", type=str, choices=["A", "B", "C"], required=True,
                       help="Studyタイプ: A（BB寄り・低ROE閾値）、B（Value寄り・ROE閾値やや高め）、C（Study A/B統合・広範囲探索）")
    parser.add_argument("--n-trials", type=int, default=200, help="試行回数（デフォルト: 200）")
    parser.add_argument("--study-name", type=str, default=None, help="スタディ名（Noneの場合は自動生成）")
    parser.add_argument("--n-jobs", type=int, default=-1, help="trial並列数（-1でCPU数）")
    parser.add_argument("--bt-workers", type=int, default=-1, help="trial内バックテストの並列数")
    parser.add_argument("--cost-bps", type=float, default=0.0, help="取引コスト（bps、デフォルト: 0.0）")
    parser.add_argument("--storage", type=str, default=None, help="Optunaストレージ（Noneの場合はSQLite）")
    parser.add_argument("--no-db-write", action="store_true", help="最適化中にDBに書き込まない")
    parser.add_argument("--cache-dir", type=str, default="cache/features", help="キャッシュディレクトリ")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="学習データの割合（デフォルト: 0.8）")
    parser.add_argument("--random-seed", type=int, default=42, help="ランダムシード（デフォルト: 42）")
    
    args = parser.parse_args()
    
    main(
        start_date=args.start,
        end_date=args.end,
        study_type=args.study_type,
        n_trials=args.n_trials,
        study_name=args.study_name,
        n_jobs=args.n_jobs,
        bt_workers=args.bt_workers,
        cost_bps=args.cost_bps,
        storage=args.storage,
        no_db_write=args.no_db_write,
        cache_dir=args.cache_dir,
        train_ratio=args.train_ratio,
        random_seed=args.random_seed,
    )

