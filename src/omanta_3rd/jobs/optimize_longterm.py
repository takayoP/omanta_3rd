"""長期保有型のパラメータ最適化システム【長期保有型用】

長期保有型のパラメータ最適化スクリプト。

リバランス日基準でランダムに学習/テストデータを分割し、過学習を抑制します。
長期保有型なので、月次リバランス型の標準的な評価指標（Sharpe ratio等）は計算しません。

【注意】このスクリプトは長期保有型専用です。
月次リバランス型の最適化には optimize_timeseries.py を使用してください。

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
import hashlib
from dataclasses import dataclass, replace, fields
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Optional, Tuple, Any, Literal
import numpy as np
import pandas as pd
import optuna
from optuna.trial import TrialState
from optuna.visualization import plot_optimization_history, plot_param_importances

from ..infra.db import connect_db
from ..jobs.longterm_run import (
    StrategyParams,
    build_features,
    select_portfolio,
    save_features,
    save_portfolio,
    _snap_price_date,
)
from ..jobs.batch_longterm_run import get_monthly_rebalance_dates
from ..backtest.feature_cache import FeatureCache
from ..backtest.performance import calculate_portfolio_performance
from ..jobs.optimize import (
    EntryScoreParams,
)

# optimize_timeseries.pyから必要な関数をインポート
from .optimize_timeseries import (
    _select_portfolio_for_rebalance_date,
    _setup_blas_threads,
)


def _calculate_performance_single_longterm(
    rebalance_date: str,
    eval_date: str,
    portfolio_df_dict: dict,
) -> Optional[Dict[str, Any]]:
    """
    単一のリバランス日に対するパフォーマンス計算のみ（並列化用）
    
    Args:
        rebalance_date: リバランス日
        eval_date: 評価日
        portfolio_df_dict: ポートフォリオDataFrameを辞書化したもの（{'index': [...], 'data': {...}}形式）
    
    Returns:
        パフォーマンス指標の辞書、エラー時はNone
    """
    try:
        from ..infra.db import connect_db
        from ..jobs.longterm_run import save_portfolio
        from ..backtest.performance import calculate_portfolio_performance
        import pandas as pd
        
        # ポートフォリオDataFrameを復元
        if '_index' in portfolio_df_dict:
            index = portfolio_df_dict.pop('_index')
            portfolio_df = pd.DataFrame.from_dict(portfolio_df_dict, orient='index')
            portfolio_df.index = index
        else:
            portfolio_df = pd.DataFrame.from_dict(portfolio_df_dict, orient='index')
        
        # DB接続を各プロセスで作成
        with connect_db() as conn:
            # ポートフォリオをDBに保存
            save_portfolio(conn, portfolio_df)
            conn.commit()
            
            # パフォーマンスを計算
            perf = calculate_portfolio_performance(rebalance_date, eval_date)
            if "error" not in perf:
                return perf
            else:
                print(f"      [_calculate_performance_single_longterm] ⚠️  {rebalance_date}のパフォーマンス計算エラー: {perf.get('error')}")
                return None
    except Exception as e:
        print(f"      [_calculate_performance_single_longterm] ⚠️  {rebalance_date}のパフォーマンス計算でエラー: {e}")
        import traceback
        traceback.print_exc()
        return None


def split_rebalance_dates(
    rebalance_dates: List[str],
    train_ratio: float = 0.8,
    random_seed: Optional[int] = 42,
    time_series_split: bool = True,
    train_end_date: Optional[str] = None,
    horizon_months: Optional[int] = None,
    require_full_horizon: bool = True,
    as_of_date: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """
    リバランス日を学習/テストに分割（固定ホライズン評価対応）
    
    Args:
        rebalance_dates: リバランス日のリスト
        train_ratio: 学習データの割合（デフォルト: 0.8、0.0 < train_ratio < 1.0）
                     train_end_dateが指定されている場合は無視される
        random_seed: ランダムシード（time_series_split=Falseの場合のみ使用）
        time_series_split: Trueの場合は時系列分割、Falseの場合はランダム分割（デフォルト: True）
                          **重要**: 運用候補を決める用途では時系列分割を推奨
        train_end_date: 学習期間の終了日（YYYY-MM-DD、Noneの場合はtrain_ratioを使用）
                       **重要**: 時系列リーク対策のため、明示的に指定することを推奨
        horizon_months: 投資ホライズン（月数、Noneの場合は固定ホライズン制約を適用しない）
        require_full_horizon: 固定ホライズン制約を適用するか（デフォルト: True）
                             Trueの場合、train期間では`eval_end <= train_end_date`を満たすものだけを使用
        as_of_date: 評価の打ち切り日（YYYY-MM-DD、Noneの場合は制限なし）
                   24Mホライズンの場合、test_datesを`as_of_date - 24M`以前に制限するために使用
    
    Returns:
        (train_dates, test_dates) のタプル
    
    Raises:
        ValueError: train_ratioが範囲外、またはrebalance_datesが2未満の場合
    """
    # バリデーション
    if train_end_date is None and not 0.0 < train_ratio < 1.0:
        raise ValueError(f"train_ratio must be in (0, 1), got {train_ratio}")
    if len(rebalance_dates) < 2:
        raise ValueError(f"rebalance_dates must have at least 2 dates, got {len(rebalance_dates)}")
    
    # 重複を除去（念のため）
    unique_dates = sorted(list(dict.fromkeys(rebalance_dates)))  # 時系列順にソート
    
    if len(unique_dates) < 2:
        raise ValueError(f"After removing duplicates, rebalance_dates must have at least 2 dates, got {len(unique_dates)}")
    
    if time_series_split:
        # 時系列分割（未来参照リーク対策）
        if train_end_date is not None:
            # train_end_dateが指定されている場合、その日付以前を学習期間とする
            candidate_train_dates = [d for d in unique_dates if d <= train_end_date]
            test_dates = [d for d in unique_dates if d > train_end_date]
            
            # 固定ホライズン制約を適用（train期間では`eval_end <= train_end_date`を満たすものだけを使用）
            if require_full_horizon and horizon_months is not None:
                train_end_dt = datetime.strptime(train_end_date, "%Y-%m-%d")
                train_dates = []
                for rebalance_date in candidate_train_dates:
                    rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
                    eval_end_dt = rebalance_dt + relativedelta(months=horizon_months)
                    if eval_end_dt <= train_end_dt:
                        train_dates.append(rebalance_date)
            else:
                train_dates = candidate_train_dates
            
            # 24Mホライズンの場合、test_datesをas_of_dateで評価可能な範囲に制限
            # これにより、test期間の評価で「ホライズン未達」が発生しないようにする
            if horizon_months == 24 and as_of_date and require_full_horizon:
                as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
                # eval_end <= as_of_date を満たすtest_datesのみを使用
                # つまり、rebalance_date + 24M <= as_of_date を満たすもの
                max_rebalance_dt = as_of_dt - relativedelta(months=horizon_months)
                max_rebalance_date = max_rebalance_dt.strftime("%Y-%m-%d")
                
                original_test_count = len(test_dates)
                test_dates = [d for d in test_dates if d <= max_rebalance_date]
                
                if len(test_dates) < original_test_count:
                    print(f"      [split_rebalance_dates] 24Mホライズンのため、test_datesを{max_rebalance_date}以前に制限しました")
                    print(f"      元のtest_dates数: {original_test_count} → 制限後: {len(test_dates)}")
            
            # バリデーション
            if len(train_dates) < 1:
                if require_full_horizon and horizon_months is not None:
                    raise ValueError(
                        f"No train dates found with eval_end <= {train_end_date} "
                        f"(horizon_months={horizon_months}, require_full_horizon=True)"
                    )
                else:
                    raise ValueError(f"No train dates found before or on {train_end_date}")
            if len(test_dates) < 1:
                # 24Mホライズンの場合、test_datesが空になることがあるが、
                # compare_lambda_penaltiesで別途調整されるため、警告のみ出す
                if horizon_months == 24 and as_of_date and require_full_horizon:
                    # max_rebalance_dateを計算
                    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
                    max_rebalance_dt = as_of_dt - relativedelta(months=horizon_months)
                    max_rebalance_date = max_rebalance_dt.strftime("%Y-%m-%d")
                    print(f"⚠️  警告: test_datesが空です（train_end_date={train_end_date}, as_of_date={as_of_date}, "
                          f"max_rebalance_date={max_rebalance_date}）。"
                          f"compare_lambda_penaltiesで別途調整されます。")
                    # test_datesを空のリストとして返す（エラーにしない）
                else:
                    raise ValueError(f"No test dates found after {train_end_date}")
        else:
            # train_ratioを使用（固定ホライズン制約は適用しない）
            n_train = int(round(len(unique_dates) * train_ratio))
            n_train = max(1, min(len(unique_dates) - 1, n_train))  # 1 <= n_train <= len-1
            
            train_dates = unique_dates[:n_train]
            test_dates = unique_dates[n_train:]
    else:
        # ランダム分割（研究用途のみ）
        # train_end_dateはランダム分割では使用できない
        if train_end_date is not None:
            raise ValueError("train_end_date cannot be used with time_series_split=False")
        
        shuffled = unique_dates.copy()
        
        # 副作用のないローカルRNGを使用（グローバル乱数状態を汚さない）
        if random_seed is not None:
            rng = random.Random(random_seed)
        else:
            rng = random.Random()  # OS乱数を使用（非再現）
        rng.shuffle(shuffled)
        
        # 学習/テストに分割
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
    horizon_months: Optional[int] = None,
    require_full_horizon: bool = True,
    as_of_date: Optional[str] = None,
    debug_rebalance_dates: Optional[set] = None,
) -> Dict[str, Any]:
    """
    長期保有型のパフォーマンスを計算（固定ホライズン評価）
    
    Args:
        rebalance_dates: リバランス日のリスト
        strategy_params: StrategyParams
        entry_params: EntryScoreParams
        cost_bps: 取引コスト（bps、デフォルト: 0.0）
        n_jobs: 並列実行数（-1でCPU数）
        features_dict: 特徴量辞書（{rebalance_date: features_df}）
        prices_dict: 価格データ辞書（{rebalance_date: {code: [adj_close, ...]}}）
        horizon_months: 投資ホライズン（月数、必須）
        require_full_horizon: ホライズン未達の期間を除外するか（デフォルト: True）
        as_of_date: 評価の打ち切り日（YYYY-MM-DD、必須）
                    **重要**: 未来参照リークを防ぐため、必ず明示的に指定してください（例: end_dateを渡す）
                    Noneの場合はエラーを発生させます（DB MAX(date)は使用しません）
        debug_rebalance_dates: デバッグ出力するリバランス日のセット（Noneの場合は出力なし）
    
    Returns:
        パフォーマンス指標の辞書
    """
    print(f"      [calculate_longterm_performance] 関数開始 (rebalance_dates数: {len(rebalance_dates)})")
    import sys
    sys.stdout.flush()
    
    import multiprocessing as mp
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
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
    # ProcessPoolExecutorを優先使用（CPU集約的なタスクのため）
    # Windowsで失敗した場合はThreadPoolExecutorにフォールバック
    if n_jobs > 1 and len(rebalance_dates) > 1:
        from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
        try:
            print(f"      [calculate_longterm_performance] 並列実行モード (max_workers={n_jobs}, ProcessPoolExecutor)")
            sys.stdout.flush()
            with ProcessPoolExecutor(max_workers=n_jobs) as executor:
                futures = {
                    executor.submit(
                        _select_portfolio_for_rebalance_date,
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
                        # 逐次実行にフォールバック
                        try:
                            portfolio = _select_portfolio_for_rebalance_date(
                                rebalance_date,
                                strategy_params_dict,
                                entry_params_dict,
                                features_dict.get(rebalance_date) if features_dict else None,
                                prices_dict.get(rebalance_date) if prices_dict else None,
                            )
                            if portfolio is not None and not portfolio.empty:
                                portfolios[rebalance_date] = portfolio
                        except Exception as e2:
                            print(f"      [calculate_longterm_performance] ⚠️  {rebalance_date}の逐次実行も失敗: {e2}")
        except Exception as e:
            # ProcessPoolExecutorが失敗した場合（Windows等）はThreadPoolExecutorにフォールバック
            print(f"      [calculate_longterm_performance] ⚠️  ProcessPoolExecutorに失敗、ThreadPoolExecutorに切り替え: {e}")
            sys.stdout.flush()
            try:
                with ThreadPoolExecutor(max_workers=n_jobs) as executor:
                    futures = {
                        executor.submit(
                            _select_portfolio_for_rebalance_date,
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
                        except Exception as e2:
                            print(f"エラー ({rebalance_date}): {e2}")
                            # 逐次実行にフォールバック
                            try:
                                portfolio = _select_portfolio_for_rebalance_date(
                                    rebalance_date,
                                    strategy_params_dict,
                                    entry_params_dict,
                                    features_dict.get(rebalance_date) if features_dict else None,
                                    prices_dict.get(rebalance_date) if prices_dict else None,
                                )
                                if portfolio is not None and not portfolio.empty:
                                    portfolios[rebalance_date] = portfolio
                            except Exception as e3:
                                print(f"      [calculate_longterm_performance] ⚠️  {rebalance_date}の逐次実行も失敗: {e3}")
            except Exception as e2:
                # ProcessPoolExecutorとThreadPoolExecutorの両方が失敗した場合は逐次実行
                print(f"      [calculate_longterm_performance] ⚠️  並列実行に完全に失敗、逐次実行に切り替え: {e2}")
                sys.stdout.flush()
                for i, rebalance_date in enumerate(rebalance_dates, 1):
                    print(f"      [calculate_longterm_performance] 処理中 ({i}/{len(rebalance_dates)}): {rebalance_date}")
                    sys.stdout.flush()
                    portfolio = _select_portfolio_for_rebalance_date(
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
    else:
        # 逐次実行
        print(f"      [calculate_longterm_performance] 逐次実行モード")
        sys.stdout.flush()
        for i, rebalance_date in enumerate(rebalance_dates, 1):
            print(f"      [calculate_longterm_performance] 処理中 ({i}/{len(rebalance_dates)}): {rebalance_date}")
            sys.stdout.flush()
            portfolio = _select_portfolio_for_rebalance_date(
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
    skipped_count = 0
    skipped_reasons = {}
    
    # 評価の打ち切り日を決定（必須）
    if as_of_date is None:
        raise ValueError(
            "as_of_dateは必須です。未来参照リークを防ぐため、"
            "必ず明示的に指定してください（例: end_dateを渡す）。"
        )
    print(f"      [calculate_longterm_performance] 評価の打ち切り日: {as_of_date}")
    
    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    
    # horizon_monthsは必須
    if horizon_months is None:
        raise ValueError("horizon_monthsは必須です。未来参照リークを防ぐため、明示的に指定してください。")
    
    # まず、評価日の計算とスナップ処理を実行（並列化前の前処理）
    portfolio_tasks = []  # [(rebalance_date, portfolio_df, eval_date), ...]
    
    with connect_db() as conn:
        for rebalance_date in sorted(portfolios.keys()):
            portfolio_df = portfolios[rebalance_date]
            
            # デバッグ: ポートフォリオの銘柄数を確認
            if len(portfolio_df) == 0:
                skipped_count += 1
                skipped_reasons["空ポートフォリオ"] = skipped_reasons.get("空ポートフォリオ", 0) + 1
                continue
            
            # 評価終了日を計算（固定ホライズン）
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_end_dt = rebalance_dt + relativedelta(months=horizon_months)
            eval_end_date = eval_end_dt.strftime("%Y-%m-%d")
            
            # require_full_horizonがTrueの場合、eval_end_dateがas_of_dateより後の場合は除外
            if require_full_horizon:
                if eval_end_dt > as_of_dt:
                    skipped_count += 1
                    skipped_reasons["ホライズン未達"] = skipped_reasons.get("ホライズン未達", 0) + 1
                    if skipped_reasons["ホライズン未達"] <= 5:  # 最初の5件だけ詳細ログ
                        print(f"      [calculate_longterm_performance] ⚠️  {rebalance_date}はホライズン未達（{horizon_months}M、eval_end={eval_end_date} > as_of={as_of_date}）のため除外")
                    continue
            
            # eval_end_dateとas_of_dateのうち、早い方を使用（安全のため）
            eval_date = min(eval_end_date, as_of_date)
            
            # require_full_horizon=Trueの場合は、固定ホライズン評価を保証するためのアサーション
            if require_full_horizon:
                assert eval_date == eval_end_date, (
                    f"require_full_horizon=True but eval_date({eval_date}) != eval_end_date({eval_end_date}). "
                    f"This should not happen if require_full_horizon check passed."
                )
            
            # eval_dateを営業日にスナップ
            try:
                eval_date_snapped = _snap_price_date(conn, eval_date)
                eval_dt = datetime.strptime(eval_date, "%Y-%m-%d")
                eval_snapped_dt = datetime.strptime(eval_date_snapped, "%Y-%m-%d")
                snap_diff_days = (eval_dt - eval_snapped_dt).days
                
                if snap_diff_days > 7:  # 1週間以上のズレは除外
                    skipped_count += 1
                    skipped_reasons[f"スナップ差分過大（{snap_diff_days}日）"] = skipped_reasons.get(f"スナップ差分過大（{snap_diff_days}日）", 0) + 1
                    print(f"      [calculate_longterm_performance] ⚠️  {rebalance_date}のeval_dateスナップ差分が大きい（{snap_diff_days}日）のため除外: {eval_date} → {eval_date_snapped}")
                    continue
                
                if eval_date_snapped != eval_date:
                    print(f"      [calculate_longterm_performance] eval_dateを営業日にスナップ: {eval_date} → {eval_date_snapped} (差分: {snap_diff_days}日)")
                eval_date = eval_date_snapped
            except RuntimeError as e:
                skipped_count += 1
                skipped_reasons["営業日スナップ失敗"] = skipped_reasons.get("営業日スナップ失敗", 0) + 1
                print(f"      [calculate_longterm_performance] ⚠️  {rebalance_date}のeval_date({eval_date})以前に営業日が見つかりません: {e}")
                continue
            
            # ログ出力（未来参照リーク確認用）
            holding_years = (datetime.strptime(eval_date, "%Y-%m-%d") - rebalance_dt).days / 365.25
            print(f"      [calculate_longterm_performance] {rebalance_date} → eval_end={eval_date} (holding={holding_years:.2f}年, horizon={horizon_months}M)")
            
            # ポートフォリオDataFrameを辞書化（pickle可能にするため）
            portfolio_df_dict = portfolio_df.to_dict(orient='index')
            # indexも保存
            portfolio_df_dict['_index'] = list(portfolio_df.index)
            
            portfolio_tasks.append((rebalance_date, portfolio_df_dict, eval_date))
    
    # パフォーマンス計算を並列実行
    if len(portfolio_tasks) == 0:
        print(f"      [calculate_longterm_performance] ⚠️  パフォーマンス計算対象が0件です")
    else:
        perf_n_jobs = min(len(portfolio_tasks), n_jobs) if n_jobs > 1 else 1
        if perf_n_jobs > 1 and len(portfolio_tasks) > 1:
            print(f"      [calculate_longterm_performance] パフォーマンス計算を並列実行 (max_workers={perf_n_jobs}, ProcessPoolExecutor)")
            sys.stdout.flush()
            from concurrent.futures import ProcessPoolExecutor, as_completed
            
            try:
                with ProcessPoolExecutor(max_workers=perf_n_jobs) as executor:
                    futures = {
                        executor.submit(
                            _calculate_performance_single_longterm,
                            rebalance_date,
                            eval_date,
                            portfolio_df_dict,
                        ): rebalance_date
                        for rebalance_date, portfolio_df_dict, eval_date in portfolio_tasks
                    }
                    
                    for future in as_completed(futures):
                        rebalance_date = futures[future]
                        try:
                            perf = future.result()
                            if perf is not None:
                                performances.append(perf)
                        except Exception as e:
                            print(f"      [calculate_longterm_performance] ⚠️  {rebalance_date}のパフォーマンス計算でエラー: {e}")
                            skipped_count += 1
                            skipped_reasons["パフォーマンス計算エラー"] = skipped_reasons.get("パフォーマンス計算エラー", 0) + 1
            except Exception as e:
                # ProcessPoolExecutorが失敗した場合（Windows等）は逐次実行にフォールバック
                print(f"      [calculate_longterm_performance] ⚠️  並列実行に失敗したため、逐次実行に切り替えます: {e}")
                sys.stdout.flush()
                for rebalance_date, portfolio_df_dict, eval_date in portfolio_tasks:
                    try:
                        perf = _calculate_performance_single_longterm(rebalance_date, eval_date, portfolio_df_dict)
                        if perf is not None:
                            performances.append(perf)
                    except Exception as e2:
                        print(f"      [calculate_longterm_performance] ⚠️  {rebalance_date}のパフォーマンス計算でエラー: {e2}")
                        skipped_count += 1
                        skipped_reasons["パフォーマンス計算エラー"] = skipped_reasons.get("パフォーマンス計算エラー", 0) + 1
        else:
            # 逐次実行
            print(f"      [calculate_longterm_performance] パフォーマンス計算を逐次実行")
            sys.stdout.flush()
            for rebalance_date, portfolio_df_dict, eval_date in portfolio_tasks:
                try:
                    perf = _calculate_performance_single_longterm(rebalance_date, eval_date, portfolio_df_dict)
                    if perf is not None:
                        performances.append(perf)
                except Exception as e:
                    print(f"      [calculate_longterm_performance] ⚠️  {rebalance_date}のパフォーマンス計算でエラー: {e}")
                    skipped_count += 1
                    skipped_reasons["パフォーマンス計算エラー"] = skipped_reasons.get("パフォーマンス計算エラー", 0) + 1
    
    # デバッグ出力（指定されたrebalance_dateのみ）
    if debug_rebalance_dates and len(performances) > 0:
        # rebalance_dateからeval_dateを取得するためのマッピングを作成
        rebalance_to_eval = {rd: ed for rd, _, ed in portfolio_tasks}
        
        for perf in performances:
            rebalance_date = perf.get("rebalance_date")
            if rebalance_date in debug_rebalance_dates:
                eval_date = rebalance_to_eval.get(rebalance_date)
                if eval_date:
                    portfolio_df = portfolios.get(rebalance_date)
                    if portfolio_df is not None:
                        selected_codes = list(portfolio_df.index)
                        weights = [float(row.get("weight", 0.0)) for _, row in portfolio_df.iterrows()]
                        
                        # 年率化リターンを計算
                        rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
                        eval_dt = datetime.strptime(eval_date, "%Y-%m-%d")
                        holding_years = (eval_dt - rebalance_dt).days / 365.25
                        
                        total_return_pct = perf.get("total_return_pct")
                        topix_comparison = perf.get("topix_comparison", {})
                        topix_return_pct = topix_comparison.get("topix_return_pct")
                        
                        annualized_total_return_pct = None
                        annualized_topix_return_pct = None
                        annualized_excess_return_pct = None
                        
                        if total_return_pct is not None and not pd.isna(total_return_pct) and holding_years > 0:
                            return_factor = 1 + total_return_pct / 100
                            if return_factor > 0:
                                annualized_total_return = return_factor ** (1 / holding_years) - 1
                                annualized_total_return_pct = annualized_total_return * 100
                                
                                if topix_return_pct is not None and not pd.isna(topix_return_pct):
                                    topix_return_factor = 1 + topix_return_pct / 100
                                    if topix_return_factor > 0:
                                        annualized_topix_return = topix_return_factor ** (1 / holding_years) - 1
                                        annualized_topix_return_pct = annualized_topix_return * 100
                                        annualized_excess_return_pct = annualized_total_return_pct - annualized_topix_return_pct
                        
                        # params_hashを計算
                        params_dict = {
                            "w_quality": strategy_params.w_quality,
                            "w_value": strategy_params.w_value,
                            "w_growth": strategy_params.w_growth,
                            "w_record_high": strategy_params.w_record_high,
                            "w_size": strategy_params.w_size,
                            "w_forward_per": strategy_params.w_forward_per,
                            "w_pbr": strategy_params.w_pbr,
                            "roe_min": strategy_params.roe_min,
                            "liquidity_quantile_cut": strategy_params.liquidity_quantile_cut,
                            "rsi_base": entry_params.rsi_base,
                            "rsi_max": entry_params.rsi_max,
                            "bb_z_base": entry_params.bb_z_base,
                            "bb_z_max": entry_params.bb_z_max,
                            "bb_weight": entry_params.bb_weight,
                            "rsi_weight": entry_params.rsi_weight,
                            "rsi_min_width": entry_params.rsi_min_width,
                            "bb_z_min_width": entry_params.bb_z_min_width,
                        }
                        params_sorted = dict(sorted(params_dict.items()))
                        params_json = json.dumps(params_sorted, sort_keys=True, ensure_ascii=False)
                        params_hash = hashlib.sha1(params_json.encode('utf-8')).hexdigest()[:8]
                        
                        # portfolio_hashを計算
                        portfolio_data = {
                            "selected_codes": sorted(selected_codes),
                            "weights": sorted(weights),
                        }
                        portfolio_json = json.dumps(portfolio_data, sort_keys=True, ensure_ascii=False)
                        portfolio_hash = hashlib.sha1(portfolio_json.encode('utf-8')).hexdigest()[:8]
                        
                        # JSONL形式で出力
                        debug_info = {
                            "rebalance_date": rebalance_date,
                            "entry_date": rebalance_date,
                            "exit_date": eval_date,
                            "selected_codes": selected_codes,
                            "weights": weights,
                            "total_return_pct": float(total_return_pct) if total_return_pct is not None and not pd.isna(total_return_pct) else None,
                            "topix_return_pct": float(topix_return_pct) if topix_return_pct is not None and not pd.isna(topix_return_pct) else None,
                            "excess_return_pct": float(topix_comparison.get("excess_return_pct")) if topix_comparison.get("excess_return_pct") is not None else None,
                            "annualized_total_return_pct": float(annualized_total_return_pct) if annualized_total_return_pct is not None else None,
                            "annualized_topix_return_pct": float(annualized_topix_return_pct) if annualized_topix_return_pct is not None else None,
                            "annualized_excess_return_pct": float(annualized_excess_return_pct) if annualized_excess_return_pct is not None else None,
                            "holding_years": float(holding_years),
                            "params_hash": params_hash,
                            "portfolio_hash": portfolio_hash,
                        }
                        print(f"[DEBUG] {json.dumps(debug_info, ensure_ascii=False)}")
                        sys.stdout.flush()
    
    # 最適化中は一時的なポートフォリオなので削除（クリーンアップ）
    # 注意: 本番運用時は削除しない
    if len(portfolio_tasks) > 0:
        with connect_db() as conn:
            for rebalance_date, _, _ in portfolio_tasks:
                conn.execute(
                    "DELETE FROM portfolio_monthly WHERE rebalance_date = ?",
                    (rebalance_date,)
                )
            conn.commit()
    
    # 集計情報を出力
    total_portfolios = len(portfolios)
    evaluated_portfolios = len(performances)
    
    # 使用されたポートフォリオの最大eval_endを計算（確認用）
    max_eval_end_used = None
    if performances:
        max_eval_end_dt = None
        for perf in performances:
            perf_eval_date = perf.get("as_of_date")  # 実際に使用されたeval_date
            if perf_eval_date:
                perf_eval_dt = datetime.strptime(perf_eval_date, "%Y-%m-%d")
                if max_eval_end_dt is None or perf_eval_dt > max_eval_end_dt:
                    max_eval_end_dt = perf_eval_dt
        if max_eval_end_dt:
            max_eval_end_used = max_eval_end_dt.strftime("%Y-%m-%d")
    
    # チェックA: 固定ホライズン評価の確認（各ポートフォリオの詳細情報を出力）
    print(f"      [calculate_longterm_performance] ポートフォリオ評価集計:")
    print(f"        総ポートフォリオ数: {total_portfolios}")
    print(f"        評価成功: {evaluated_portfolios}")
    print(f"        スキップ: {skipped_count}")
    if max_eval_end_used:
        print(f"        使用されたポートフォリオの最大eval_end: {max_eval_end_used}")
    print(f"        as_of_date: {as_of_date}")
    if skipped_reasons:
        print(f"        スキップ理由内訳:")
        for reason, count in skipped_reasons.items():
            print(f"          - {reason}: {count}件")
    
    # チェックA: 各ポートフォリオのrebalance_date, eval_end_date, holding_yearsを出力
    print(f"      [calculate_longterm_performance] 【チェックA】固定ホライズン評価の確認:")
    print(f"        rebalance_date | eval_end_date | holding_years | 備考")
    print(f"        " + "-" * 70)
    rebalance_to_eval = {rd: ed for rd, _, ed in portfolio_tasks}
    for perf in sorted(performances, key=lambda p: p.get("rebalance_date", "")):
        rebalance_date = perf.get("rebalance_date")
        eval_date_used = perf.get("as_of_date")  # 実際に使用されたeval_date
        eval_end_expected = rebalance_to_eval.get(rebalance_date)  # 期待されるeval_end_date（rebalance_date + horizon_months）
        
        if rebalance_date and eval_date_used:
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_dt = datetime.strptime(eval_date_used, "%Y-%m-%d")
            holding_years = (eval_dt - rebalance_dt).days / 365.25
            
            # 期待されるeval_end_dateと実際のeval_dateが一致するか確認
            if eval_end_expected:
                eval_end_expected_dt = datetime.strptime(eval_end_expected, "%Y-%m-%d")
                if eval_date_used == eval_end_expected:
                    status = "✓ 固定ホライズン"
                else:
                    status = f"⚠️ 不一致 (期待: {eval_end_expected})"
            else:
                status = "⚠️ eval_end不明"
            
            print(f"        {rebalance_date} | {eval_date_used} | {holding_years:.2f}年 | {status}")
    
    # チェックB: train側で未来リークしていないか確認
    # 注意: rebalance_datesは関数の引数として利用可能
    if as_of_date:
        as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
        print(f"      [calculate_longterm_performance] 【チェックB】未来リーク確認:")
        print(f"        as_of_date: {as_of_date}")
        print(f"        horizon_months: {horizon_months}")
        print(f"        require_full_horizon: {require_full_horizon}")
        
        # 評価に使われたポートフォリオのrebalance_dateを確認
        used_rebalance_dates = [p.get("rebalance_date") for p in performances if p.get("rebalance_date")]
        if used_rebalance_dates:
            latest_rebalance = max(used_rebalance_dates)
            latest_rebalance_dt = datetime.strptime(latest_rebalance, "%Y-%m-%d")
            expected_max_eval = latest_rebalance_dt + relativedelta(months=horizon_months)
            
            print(f"        評価に使用された最新のrebalance_date: {latest_rebalance}")
            print(f"        期待される最大eval_end: {expected_max_eval.strftime('%Y-%m-%d')}")
            
            if expected_max_eval <= as_of_dt:
                print(f"        ✓ 未来リークなし（期待される最大eval_end <= as_of_date）")
            else:
                print(f"        ⚠️  警告: 期待される最大eval_end > as_of_date（未来リークの可能性）")
            
            # train期間の終盤（最後の10%）が評価に使われているか確認
            # rebalance_datesは関数の引数として利用可能
            if len(rebalance_dates) > 0:
                sorted_dates = sorted(rebalance_dates)
                train_cutoff_idx = int(len(sorted_dates) * 0.9)  # 最後の10%
                train_cutoff_date = sorted_dates[train_cutoff_idx] if train_cutoff_idx < len(sorted_dates) else sorted_dates[-1]
                train_cutoff_dt = datetime.strptime(train_cutoff_date, "%Y-%m-%d")
                
                late_train_portfolios = [rd for rd in used_rebalance_dates if datetime.strptime(rd, "%Y-%m-%d") >= train_cutoff_dt]
                if late_train_portfolios:
                    print(f"        ⚠️  警告: train期間の終盤（{train_cutoff_date}以降）のポートフォリオが評価に使用されています:")
                    for rd in sorted(late_train_portfolios):
                        print(f"          - {rd}")
                else:
                    print(f"        ✓ train期間の終盤は評価に使用されていません（未来リークなし）")
    
    if not performances:
        raise RuntimeError(
            f"No performances were calculated. "
            f"Total portfolios: {len(portfolios)}, Skipped: {skipped_count}, "
            f"Reasons: {skipped_reasons}"
        )
    
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
            # 保有期間を計算（eval_dateを使用）
            rebalance_dt = dt.strptime(rebalance_date, "%Y-%m-%d")
            eval_dt = dt.strptime(perf.get("as_of_date", as_of_date), "%Y-%m-%d")
            holding_years = (eval_dt - rebalance_dt).days / 365.25
            
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
                # 変更: 年率化してから差を取る方法に統一（avg_annualized_excess_return_pctと一致させるため）
                # 式: (1+total)^(1/t) - (1+topix)^(1/t)
                topix_return_pct = topix_comparison.get("topix_return_pct")
                if topix_return_pct is not None and not pd.isna(topix_return_pct):
                    # 年率TOPIXリターンを計算
                    topix_return_factor = 1 + topix_return_pct / 100
                    if topix_return_factor > 0:
                        annual_topix_return = topix_return_factor ** (1 / holding_years) - 1
                        annual_topix_return_pct = annual_topix_return * 100
                        # 複素数チェック（念のため）
                        if isinstance(annual_topix_return_pct, complex):
                            # 複素数の場合はスキップ
                            print(f"警告: {rebalance_date}の年率TOPIXリターンが複素数になりました。累積TOPIXリターン: {topix_return_pct:.2f}%, 保有期間: {holding_years:.2f}年")
                        else:
                            # 年率超過リターン = 年率総リターン - 年率TOPIXリターン
                            annual_excess_return_pct = annual_return_pct - annual_topix_return_pct
                            annual_excess_returns.append(annual_excess_return_pct)
                    else:
                        # 累積TOPIXリターンが-100%未満の場合はスキップ（年率化不可）
                        print(f"警告: {rebalance_date}の累積TOPIXリターンが-100%未満のため、年率化をスキップします。累積TOPIXリターン: {topix_return_pct:.2f}%")
                elif excess_return_pct is not None and not pd.isna(excess_return_pct):
                    # フォールバック: TOPIXリターンが取得できない場合は、累積超過を年率化（後方互換性のため）
                    # 注意: 通常は発生しないが、データ欠損の場合のフォールバック
                    excess_factor = 1 + excess_return_pct / 100
                    if excess_factor > 0:
                        annual_excess_return = excess_factor ** (1 / holding_years) - 1
                        annual_excess_return_pct = annual_excess_return * 100
                        if not isinstance(annual_excess_return_pct, complex):
                            annual_excess_returns.append(annual_excess_return_pct)
            
            total_returns.append(total_return_pct)
            # excess_return_pctもNone/NaNチェック（累積値、参考用）
            if excess_return_pct is not None and not pd.isna(excess_return_pct):
                excess_returns.append(excess_return_pct)
    
    # 集計指標を計算
    # 目的関数: 各ポートフォリオの年率超過リターンの平均（TOPIXに対する超過リターン）
    # 変更: 年率化してから差を取る方法に統一（avg_annualized_excess_return_pctと一致）
    # 式: mean([(1+total_i/100)^(1/t_i) - 1] - [(1+topix_i/100)^(1/t_i) - 1])
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
    end_dt = as_of_dt
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
    
    # 下振れ指標（P10、P25、min）を計算
    p10_annual_excess_return = np.percentile(annual_excess_returns, 10.0) if annual_excess_returns else 0.0
    p25_annual_excess_return = np.percentile(annual_excess_returns, 25.0) if annual_excess_returns else 0.0
    min_annual_excess_return = np.min(annual_excess_returns) if annual_excess_returns else 0.0
    
    result = {
        # 目的関数用（TOPIXに対する年率超過リターン）
        # 変更: 年率化してから差を取る方法に統一（avg_annualized_excess_return_pctと一致）
        "mean_annual_excess_return_pct": mean_annual_excess_return,  # 各ポートフォリオの年率超過リターンの平均（年率化してから差を取る方法）
        "median_annual_excess_return_pct": median_annual_excess_return,  # 中央値
        "annual_excess_returns_list": annual_excess_returns,  # 個別の年率超過リターンリスト（trimmed_mean用）
        # 下振れ指標（下振れ罰用）
        "p10_annual_excess_return_pct": p10_annual_excess_return,  # 下位10%の平均超過リターン
        "p25_annual_excess_return_pct": p25_annual_excess_return,  # 下位25%の平均超過リターン
        "min_annual_excess_return_pct": min_annual_excess_return,  # 最小超過リターン
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
        "n_periods": len(annual_excess_returns),  # P10算出に使ったサンプル数（ChatGPT推奨）
        "mean_holding_years": mean_holding_years,
        "total_years": total_years,
        "first_rebalance": first_rebalance,
        "as_of_date": as_of_date,
        "last_date": as_of_date,  # 後方互換性のため
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
    horizon_months: int = 24,
    require_full_horizon: bool = True,
    as_of_date: Optional[str] = None,
    lambda_penalty: float = 0.0,
    objective_type: str = "mean",  # "mean", "median", "trimmed_mean"
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
        horizon_months: 投資ホライズン（月数、デフォルト: 24）
        require_full_horizon: ホライズン未達の期間を除外するか（デフォルト: True）
        as_of_date: 評価の打ち切り日（YYYY-MM-DD、Noneの場合はend_dateを使用）
    
    Returns:
        最適化対象の値（年率超過リターン、TOPIXに対する超過リターン）
    """
    print(f"    [objective_longterm] 関数開始 (Trial {trial.number})")
    import sys
    sys.stdout.flush()
    
    # StrategyParamsのパラメータ
    # 意味のある範囲で自由に探索（Study C用に拡張）
    print(f"    [objective_longterm] パラメータ提案開始...")
    sys.stdout.flush()
    
    # Study A/B/Cで異なる範囲
    if study_type == "A":
        # Study A: BB寄り・低ROE閾値
        w_quality = trial.suggest_float("w_quality", 0.05, 0.50)
        w_growth = trial.suggest_float("w_growth", 0.01, 0.30)
        w_record_high = trial.suggest_float("w_record_high", 0.01, 0.20)
        w_size = trial.suggest_float("w_size", 0.05, 0.40)
        w_value = trial.suggest_float("w_value", 0.10, 0.50)
        w_forward_per = trial.suggest_float("w_forward_per", 0.20, 0.90)
        roe_min = trial.suggest_float("roe_min", 0.00, 0.12)
        bb_weight = trial.suggest_float("bb_weight", 0.30, 0.95)
    elif study_type == "B":
        # Study B: Value寄り・ROE閾値やや高め（ただし、より広い範囲で探索）
        w_quality = trial.suggest_float("w_quality", 0.05, 0.50)
        w_growth = trial.suggest_float("w_growth", 0.01, 0.30)
        w_record_high = trial.suggest_float("w_record_high", 0.01, 0.20)
        w_size = trial.suggest_float("w_size", 0.05, 0.40)
        w_value = trial.suggest_float("w_value", 0.20, 0.60)
        w_forward_per = trial.suggest_float("w_forward_per", 0.20, 0.80)
        roe_min = trial.suggest_float("roe_min", 0.00, 0.20)
        bb_weight = trial.suggest_float("bb_weight", 0.20, 0.80)
    else:  # study_type == "C"
        # Study C: 意味のある範囲で自由に探索（拡張版）
        # 重みパラメータ（正規化されるため、範囲を広げても実質的な影響は限定的だが、より広い探索を可能にする）
        w_quality = trial.suggest_float("w_quality", 0.01, 0.70)  # 拡張: 0.05-0.50 → 0.01-0.70
        w_growth = trial.suggest_float("w_growth", 0.01, 0.50)  # 拡張: 0.01-0.30 → 0.01-0.50
        w_record_high = trial.suggest_float("w_record_high", 0.01, 0.30)  # 拡張: 0.01-0.20 → 0.01-0.30
        w_size = trial.suggest_float("w_size", 0.01, 0.60)  # 拡張: 0.05-0.40 → 0.01-0.60
        w_value = trial.suggest_float("w_value", 0.05, 0.80)  # 拡張: 0.10-0.60 → 0.05-0.80
        
        # Value mix（完全に自由に探索）
        w_forward_per = trial.suggest_float("w_forward_per", 0.0, 1.0)  # 拡張: 0.20-0.90 → 0.0-1.0
        
        # ROE閾値（意味のある範囲で拡張）
        roe_min = trial.suggest_float("roe_min", 0.00, 0.30)  # 拡張: 0.00-0.20 → 0.00-0.30
        
        # BB weight（完全に自由に探索）
        bb_weight = trial.suggest_float("bb_weight", 0.0, 1.0)  # 拡張: 0.20-0.95 → 0.0-1.0
        
        print(f"    [objective_longterm] w_quality取得完了: {w_quality}")
        sys.stdout.flush()
    
    # 正規化（合計が1になるように）
    total = w_quality + w_value + w_growth + w_record_high + w_size
    w_quality /= total
    w_value /= total
    w_growth /= total
    w_record_high /= total
    w_size /= total
    
    w_pbr = 1.0 - w_forward_per
    
    # 共通パラメータ
    if study_type == "C":
        # Study C: 意味のある範囲で自由に探索
        liquidity_quantile_cut = trial.suggest_float("liquidity_quantile_cut", 0.05, 0.50)  # 拡張: 0.10-0.30 → 0.05-0.50
    else:
        # Study A/B: 以前と同じ範囲に固定、比較の公平性のため
        liquidity_quantile_cut = trial.suggest_float("liquidity_quantile_cut", 0.10, 0.30)
    
    # RSIパラメータ（順張り/逆張りを対称に探索）
    RSI_LOW, RSI_HIGH = 15.0, 85.0
    rsi_min_width = 10.0  # 最小幅制約（緩和: 20.0 → 10.0）
    
    # baseを先にサンプリング（空レンジ対策: baseの範囲を制限）
    # 両方向が常に可能になるように、baseの範囲を[min_width, HIGH-min_width]に制限
    rsi_base = trial.suggest_float("rsi_base", RSI_LOW + rsi_min_width, RSI_HIGH - rsi_min_width)
    
    # baseに対して制約を満たすmaxの範囲を計算
    # maxは base ± min_width の範囲外から選ぶ必要がある
    max_low = max(RSI_LOW, rsi_base + rsi_min_width)  # 順張り方向の下限: base + min_width 以上
    max_high = min(RSI_HIGH, rsi_base - rsi_min_width)  # 逆張り方向の上限: base - min_width 以下
    
    # 制約を満たす範囲が存在するかチェック
    can_long = (max_low <= RSI_HIGH)  # 順張り方向が可能か
    can_short = (max_high >= RSI_LOW)  # 逆張り方向が可能か
    
    # baseの範囲を制限したので、通常は両方向が可能（空レンジ対策済み）
    # 念のため、方向が1つしかない場合も処理
    if can_long and can_short:
        # 両方向が可能な場合: categoricalパラメータで方向を選ぶ（再現性向上）
        # 順張り方向: [base + min_width, RSI_HIGH]
        # 逆張り方向: [RSI_LOW, base - min_width]
        rsi_direction = trial.suggest_categorical("rsi_direction", ["momentum", "reversal"])
        if rsi_direction == "momentum":
            rsi_max = trial.suggest_float("rsi_max", max_low, RSI_HIGH)
        else:  # reversal
            rsi_max = trial.suggest_float("rsi_max", RSI_LOW, max_high)
    elif can_long:
        # 順張り方向のみ可能: [base + min_width, RSI_HIGH]
        rsi_direction = "momentum"  # 自動的にmomentumに設定
        rsi_max = trial.suggest_float("rsi_max", max_low, RSI_HIGH)
    elif can_short:
        # 逆張り方向のみ可能: [RSI_LOW, base - min_width]
        rsi_direction = "reversal"  # 自動的にreversalに設定
        rsi_max = trial.suggest_float("rsi_max", RSI_LOW, max_high)
    else:
        # 制約を満たす範囲が存在しない（baseの範囲制限により通常は発生しない）
        trial.set_user_attr("prune_reason", "rsi_no_valid_range")
        raise optuna.TrialPruned(f"RSI: base={rsi_base:.2f}に対して制約を満たすmaxの範囲が存在しません")
    
    # BB Z-scoreパラメータ（順張り/逆張りを対称に探索）
    BB_LOW, BB_HIGH = -3.5, 3.5
    bb_z_min_width = 0.5  # 最小幅制約（緩和: 1.0 → 0.5）
    
    # baseを先にサンプリング（空レンジ対策: baseの範囲を制限）
    # 両方向が常に可能になるように、baseの範囲を[LOW+min_width, HIGH-min_width]に制限
    bb_z_base = trial.suggest_float("bb_z_base", BB_LOW + bb_z_min_width, BB_HIGH - bb_z_min_width)
    
    # baseに対して制約を満たすmaxの範囲を計算
    # maxは base ± min_width の範囲外から選ぶ必要がある
    bb_max_low = max(BB_LOW, bb_z_base + bb_z_min_width)  # 順張り方向の下限: base + min_width 以上
    bb_max_high = min(BB_HIGH, bb_z_base - bb_z_min_width)  # 逆張り方向の上限: base - min_width 以下
    
    # 制約を満たす範囲が存在するかチェック
    bb_can_long = (bb_max_low <= BB_HIGH)  # 順張り方向が可能か
    bb_can_short = (bb_max_high >= BB_LOW)  # 逆張り方向が可能か
    
    # baseの範囲を制限したので、通常は両方向が可能（空レンジ対策済み）
    # 念のため、方向が1つしかない場合も処理
    if bb_can_long and bb_can_short:
        # 両方向が可能な場合: categoricalパラメータで方向を選ぶ（再現性向上）
        # 順張り方向: [base + min_width, BB_HIGH]
        # 逆張り方向: [BB_LOW, base - min_width]
        bb_direction = trial.suggest_categorical("bb_direction", ["momentum", "reversal"])
        if bb_direction == "momentum":
            bb_z_max = trial.suggest_float("bb_z_max", bb_max_low, BB_HIGH)
        else:  # reversal
            bb_z_max = trial.suggest_float("bb_z_max", BB_LOW, bb_max_high)
    elif bb_can_long:
        # 順張り方向のみ可能: [base + min_width, BB_HIGH]
        bb_direction = "momentum"  # 自動的にmomentumに設定
        bb_z_max = trial.suggest_float("bb_z_max", bb_max_low, BB_HIGH)
    elif bb_can_short:
        # 逆張り方向のみ可能: [BB_LOW, base - min_width]
        bb_direction = "reversal"  # 自動的にreversalに設定
        bb_z_max = trial.suggest_float("bb_z_max", BB_LOW, bb_max_high)
    else:
        # 制約を満たす範囲が存在しない（baseの範囲制限により通常は発生しない）
        trial.set_user_attr("prune_reason", "bb_no_valid_range")
        raise optuna.TrialPruned(f"BB Z-score: base={bb_z_base:.2f}に対して制約を満たすmaxの範囲が存在しません")
    
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
    
    # 順張り/逆張りの方向と幅をログに記録（directionを必ず保存・ログ出力）
    # rsi_direction/bb_directionはcategoricalパラメータまたは自動設定された値
    # 日本語表記も保存（後で説明するのに便利）
    rsi_direction_str = "順張り" if rsi_max > rsi_base else "逆張り"
    bb_direction_str = "順張り" if bb_z_max > bb_z_base else "逆張り"
    trial.set_user_attr("rsi_direction", rsi_direction)  # "momentum" or "reversal"
    trial.set_user_attr("rsi_direction_jp", rsi_direction_str)  # "順張り" or "逆張り"
    trial.set_user_attr("bb_direction", bb_direction)  # "momentum" or "reversal"
    trial.set_user_attr("bb_direction_jp", bb_direction_str)  # "順張り" or "逆張り"
    trial.set_user_attr("rsi_width", abs(rsi_max - rsi_base))
    trial.set_user_attr("bb_z_width", abs(bb_z_max - bb_z_base))
    
    # ログ出力（directionを必ず出力）
    print(f"    [objective_longterm] RSI方向: {rsi_direction} ({rsi_direction_str}), BB方向: {bb_direction} ({bb_direction_str})")
    sys.stdout.flush()
    
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
        horizon_months=horizon_months,
        require_full_horizon=require_full_horizon,
        as_of_date=as_of_date,
    )
    print(f"    [objective_longterm] calculate_longterm_performance完了")
    sys.stdout.flush()
    
    # 目的関数: 各ポートフォリオの年率超過リターンの集計値 - 下振れ罰
    # objective_typeに応じて集計方法を変更（過学習対策）
    annual_excess_returns_list = perf.get("annual_excess_returns_list", [])  # 内部計算用（後で追加）
    mean_excess = perf["mean_annual_excess_return_pct"]
    median_excess = perf.get("median_annual_excess_return_pct", 0.0)
    p10_excess = perf.get("p10_annual_excess_return_pct", 0.0)  # 下位10%の平均超過リターン
    min_excess = perf.get("min_annual_excess_return_pct", 0.0)  # 最小超過リターン
    n_periods = perf.get("n_periods", 0)  # P10算出に使ったサンプル数（ChatGPT推奨）
    
    # サンプル数が少ない場合は警告（P10の信頼性が低い可能性がある）
    # 注意: horizon_monthsに応じて閾値を調整する必要がある（12Mなら20、24Mなら10等）
    min_periods_threshold = 20 if horizon_months <= 12 else 10  # 12Mなら20、24Mなら10
    if n_periods < min_periods_threshold:
        print(f"      [objective_longterm] ⚠️  警告: n_periods={n_periods}が少ないため、P10の信頼性が低い可能性があります（閾値: {min_periods_threshold}）")
        # 注意: trialを無効にする（-infを返す）修正も検討可能だが、現状は警告のみ
    
    # 空評価（評価不能）のチェック（強ペナルティを返す）
    # annual_excess_returns_listが空、またはn_periodsが0の場合は評価不能
    if not annual_excess_returns_list or len(annual_excess_returns_list) == 0 or n_periods == 0:
        # 評価不能な場合は強ペナルティを返す（0.0ではなく、探索が壊れないように）
        objective_value = -1e9  # 十分小さい値
        print(f"      [objective_longterm] ⚠️  警告: 評価不能（annual_excess_returns_listが空またはn_periods=0）のため、強ペナルティを返します")
        print(f"        num_portfolios: {perf.get('num_portfolios', 0)}, n_periods: {n_periods}")
        sys.stdout.flush()
        trial.set_user_attr("evaluation_failed", True)
        trial.set_user_attr("evaluation_failed_reason", "empty_annual_excess_returns")
        return objective_value
    
    # objective_typeに応じて集計値を選択（過学習対策）
    if objective_type == "median":
        # median目的（外れ値に強い）
        base_excess = median_excess
    elif objective_type == "trimmed_mean":
        # trimmed mean（上下10%をカット、外れ値に強い）
        try:
            from scipy.stats import trim_mean
            if annual_excess_returns_list and len(annual_excess_returns_list) > 0:
                base_excess = trim_mean(annual_excess_returns_list, 0.1) * 100  # パーセントに変換
            else:
                base_excess = mean_excess  # フォールバック（通常は到達しない）
        except ImportError:
            print(f"      [objective_longterm] ⚠️  scipyが利用できないため、trimmed_meanをmeanにフォールバック")
            base_excess = mean_excess
    else:  # "mean" (デフォルト)
        # mean目的（従来通り）
        base_excess = mean_excess
    
    # 下振れ罰: P10が負の場合はペナルティ、正の場合はボーナス（係数λ）
    downside_penalty = lambda_penalty * min(0.0, p10_excess)  # P10が負の場合のみペナルティ
    
    # 目的関数: 集計超過 - 下振れ罰
    objective_value = base_excess + downside_penalty
    
    # mean_excessとp10_excessをtrialに保存（将来のλ再採点用、ChatGPT推奨）
    # 注意: これにより、既存のstudy DBから異なるλ値で再採点が可能になる
    trial.set_user_attr("mean_excess", mean_excess)
    trial.set_user_attr("base_excess", base_excess)  # 実際に使用した集計値
    trial.set_user_attr("objective_type", objective_type)  # 使用した集計方法
    trial.set_user_attr("p10_excess", p10_excess)
    trial.set_user_attr("n_periods", n_periods)
    trial.set_user_attr("min_excess", min_excess)
    trial.set_user_attr("median_excess", perf["median_annual_excess_return_pct"])
    trial.set_user_attr("win_rate", perf["win_rate"])
    trial.set_user_attr("lambda_penalty", lambda_penalty)  # 使用したλ値も保存
    
    # デバッグ用ログ出力（下振れ指標を含む）
    log_msg = (
        f"[Trial {trial.number}] "
        f"objective={objective_value:.4f}% (type={objective_type}), "
        f"base_excess={base_excess:.4f}%, "
        f"mean_excess={mean_excess:.4f}%, "
        f"p10_excess={p10_excess:.4f}% (n_periods={n_periods}), "
        f"downside_penalty={downside_penalty:.4f}%, "
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
    save_params: Optional[str] = None,
    params_id: Optional[str] = None,
    version: Optional[str] = None,
        horizon_months: int = 24,
        strategy_mode: Optional[Literal["momentum", "reversal"]] = None,
        as_of_date: Optional[str] = None,
        train_end_date: Optional[str] = None,
        lambda_penalty: float = 0.0,
        force_rebuild_cache: bool = False,
        objective_type: str = "mean",  # "mean", "median", "trimmed_mean"
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
        train_ratio: 学習データの割合（デフォルト: 0.8、train_end_dateが指定されている場合は無視される）
        random_seed: ランダムシード（デフォルト: 42）
        save_params: パラメータファイルの保存パス（Noneの場合は保存しない）
        params_id: パラメータID（レジストリ用、save_paramsが指定されている場合に必要）
        version: バージョン（例: "v2", "v20260108"、Noneの場合は自動生成）
        horizon_months: 投資ホライズン（月数、デフォルト: 24）
        strategy_mode: 戦略モード（"momentum"または"reversal"、Noneの場合は自動判定）
        as_of_date: 評価の打ち切り日（YYYY-MM-DD、Noneの場合はend_dateを使用）
                    **重要**: 未来参照リークを防ぐため、end_dateをデフォルトとして使用
        train_end_date: 学習期間の終了日（YYYY-MM-DD、Noneの場合はtrain_ratioを使用）
                       **重要**: 時系列リーク対策のため、明示的に指定することを推奨
    """
    # BLASスレッドを1に設定
    _setup_blas_threads()
    
    # as_of_dateが指定されていない場合、end_dateを使用（DB MAX(date)は使わない）
    if as_of_date is None:
        as_of_date = end_date
        print(f"      [optimize_longterm_main] as_of_dateが指定されていません。end_date({as_of_date})を使用します。")
    
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
    if train_end_date is not None:
        print(f"学習期間終了日: {train_end_date}")
    else:
        print(f"学習/テスト分割: {train_ratio:.1%} / {1-train_ratio:.1%}")
    print(f"試行回数: {n_trials}")
    print(f"取引コスト: {cost_bps} bps")
    print(f"ランダムシード: {random_seed}")
    print("=" * 80)
    print()
    
    # リバランス日を取得
    # 注意: 24Mホライズンの場合、end_dateは調整されているが、
    # test_datesの決定にはas_of_date（または元のend_date）を使用する必要がある
    # そうしないと、train_end_date以降にtest_datesが存在しない可能性がある
    evaluation_end_date = as_of_date if as_of_date else end_date
    rebalance_dates = get_monthly_rebalance_dates(start_date, evaluation_end_date)
    print(f"リバランス日数: {len(rebalance_dates)}")
    print(f"最初: {rebalance_dates[0] if rebalance_dates else 'N/A'}")
    print(f"最後: {rebalance_dates[-1] if rebalance_dates else 'N/A'}")
    print()
    
    if not rebalance_dates:
        print("❌ リバランス日が見つかりませんでした")
        return
    
    # 学習/テストに分割（固定ホライズン評価対応）
    try:
        train_dates, test_dates = split_rebalance_dates(
            rebalance_dates,
            train_ratio=train_ratio,
            random_seed=random_seed,
            time_series_split=True,  # 時系列分割（未来参照リーク対策）
            train_end_date=train_end_date,
            horizon_months=horizon_months,  # 固定ホライズン制約
            require_full_horizon=True,  # train期間では`eval_end <= train_end_date`を満たすものだけを使用
            as_of_date=as_of_date,  # 24Mホライズンの場合、test_datesを制限するために使用
        )
        
        # 24Mホライズンの場合、test_datesが空になったら、compare_lambda_penaltiesと同じロジックで再計算
        if horizon_months == 24 and as_of_date and train_end_date and not test_dates:
            from datetime import datetime as dt
            as_of_dt = dt.strptime(as_of_date, "%Y-%m-%d")
            test_max_dt = as_of_dt - relativedelta(months=24)
            test_max_date = test_max_dt.strftime("%Y-%m-%d")
            
            train_end_dt = dt.strptime(train_end_date, "%Y-%m-%d")
            train_max_dt = train_end_dt - relativedelta(months=24)
            train_max_date = train_max_dt.strftime("%Y-%m-%d")
            
            # test期間は (train_max_dt, test_max_dt] に限定（train期間と重複しないように）
            # 注意: 境界の取り扱い（`>` と `<=`）により、train_max_dtと同日のrebalanceは除外される
            test_dates = []
            train_max_boundary_dates = []  # 境界確認用
            for d in rebalance_dates:
                d_dt = dt.strptime(d, "%Y-%m-%d")
                if d_dt > train_max_dt and d_dt <= test_max_dt:
                    test_dates.append(d)
                # 境界確認: train_max_dtと同日または直後のrebalanceを記録
                if abs((d_dt - train_max_dt).days) <= 5:  # 5日以内のrebalanceを記録
                    train_max_boundary_dates.append(d)
            
            if test_dates:
                print(f"⚠️  24Mホライズンのため、test_datesを再計算しました（compare_lambda_penaltiesと同じロジック）")
                print(f"   train_max_rb (train期間の最終rebalance): {train_max_date}")
                print(f"   test_max_rb (test期間の最終rebalance): {test_max_date}")
                print(f"   件数: {len(test_dates)}")
                print(f"   最初: {test_dates[0] if test_dates else 'N/A'}")
                print(f"   最後: {test_dates[-1] if test_dates else 'N/A'}")
                # 境界確認ログ
                if train_max_boundary_dates:
                    print(f"   [境界確認] train_max_rb付近のrebalance: {train_max_boundary_dates}")
                    # train_datesの最終日とtest_datesの最初日が重複していないことを確認
                    if train_dates and test_dates:
                        train_last_dt = dt.strptime(train_dates[-1], "%Y-%m-%d")
                        test_first_dt = dt.strptime(test_dates[0], "%Y-%m-%d")
                        if train_last_dt >= test_first_dt:
                            print(f"   ⚠️  警告: train_datesの最終日({train_dates[-1]}) >= test_datesの最初日({test_dates[0]}) - 重複の可能性")
                        else:
                            print(f"   ✓ 境界確認OK: train_datesの最終日({train_dates[-1]}) < test_datesの最初日({test_dates[0]})")
            else:
                print(f"⚠️  警告: test_datesが空です（train_max_rb: {train_max_date}, test_max_rb: {test_max_date}）。")
                print(f"   compare_lambda_penaltiesで別途調整されます。")
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
        n_jobs=bt_workers if bt_workers > 0 else -1,
        force_rebuild=force_rebuild_cache
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
    
    # 既存のtrial数を確認（load_if_exists=Trueの場合）
    existing_trials = len(study.trials)
    existing_completed = len([t for t in study.trials if t.state == TrialState.COMPLETE])
    if existing_trials > 0:
        print(f"既存のstudyを読み込みました（既存trial数: {existing_trials}, 完了: {existing_completed}）")
        print(f"新規に{n_trials}回の正常計算を追加します（合計目標: {existing_completed + n_trials}回の完了trial）")
        
        # 既存の完了trial数が既に目標を超えている場合の警告
        if existing_completed >= n_trials:
            print(f"⚠️  警告: 既存の完了trial数（{existing_completed}）が要求数（{n_trials}）を既に超えています。")
            print(f"   新規の最適化は実行されません。既存の結果を使用します。")
            print(f"   新しい最適化を実行する場合は、既存のstudyを削除するか、異なるstudy_nameを指定してください。")
            print()
        else:
            print()
    
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
        # より積極的に並列化（CPU数に応じて調整）
        # バックテストはCPU集約的なため、利用可能なCPUを最大限活用
        backtest_n_jobs = max(1, min(len(train_dates), available_cpus))
        if len(train_dates) >= 4 and available_cpus >= 4:
            # 4つ以上のCPUがある場合は、より積極的に並列化
            backtest_n_jobs = max(4, min(len(train_dates), min(8, available_cpus)))
        elif len(train_dates) >= 2 and available_cpus >= 2:
            backtest_n_jobs = max(2, min(len(train_dates), min(4, available_cpus)))
    else:
        backtest_n_jobs = bt_workers
    
    print("最適化を開始します...")
    print(f"CPU数: {cpu_count}")
    print(f"Optuna試行並列数: {optuna_n_jobs}")
    print(f"各試行内のバックテスト並列数: {backtest_n_jobs}")
    print()
    
    # 最適化実行（完了したtrial数が指定数に達するまでループ）
    objective_fn = lambda trial: objective_longterm(
        trial,
        train_dates,
        study_type,
        cost_bps,
        backtest_n_jobs,
        features_dict=features_dict,
        prices_dict=prices_dict,
        horizon_months=horizon_months,
        require_full_horizon=True,  # ホライズン未達の期間を除外
        as_of_date=as_of_date,
        lambda_penalty=lambda_penalty,
        objective_type=objective_type,
    )
    
    # 既存の完了trial数を考慮
    initial_completed = existing_completed
    target_completed = initial_completed + n_trials
    completed_trials = initial_completed
    iteration = 0
    max_iterations = n_trials * 3  # 無限ループ防止（最大3倍まで試行）
    
    print(f"最適化を開始します（正常に計算が完了したtrial数が{target_completed}に達するまで実行）...")
    print(f"  既存の完了trial: {initial_completed}回")
    print(f"  新規に必要な完了trial: {n_trials}回")
    print()
    
    while completed_trials < target_completed and iteration < max_iterations:
        iteration += 1
        remaining = target_completed - completed_trials
        
        # 既存の完了trial数が既に目標を超えている場合は、最適化をスキップ
        if remaining <= 0:
            print(f"✓ 既存の完了trial数（{completed_trials}）が既に目標（{target_completed}）を満たしています。")
            print(f"  新規の最適化は実行されません。既存の結果を使用します。")
            break
        
        # 残りの試行数を実行
        # 注意: 進捗バーは既存のtrialも含めてカウントするため、表示がずれる可能性がある
        # そのため、進捗バーは表示しない（手動でログを出力する）
        show_progress = False  # 進捗バーは表示しない（trial番号がずれるため）
        
        print(f"  新規trialを{remaining}回実行します（iteration {iteration}/{max_iterations}）...")
        study.optimize(
            objective_fn,
            n_trials=remaining,
            show_progress_bar=show_progress,
            n_jobs=optuna_n_jobs,
        )
        
        # 完了したtrial数をカウント（COMPLETE状態のみ = 正常に計算が完了したtrial）
        completed_trials = len([
            t for t in study.trials 
            if t.state == TrialState.COMPLETE
        ])
        
        complete_count = completed_trials
        pruned_count = len([t for t in study.trials if t.state == TrialState.PRUNED])
        fail_count = len([t for t in study.trials if t.state == TrialState.FAIL])
        total_trials = len(study.trials)
        new_completed = completed_trials - initial_completed
        
        if completed_trials < target_completed:
            print(f"  完了trial数: {completed_trials}/{target_completed}（新規完了: {new_completed}/{n_trials}, 総試行数: {total_trials}, pruned: {pruned_count}, fail: {fail_count}）")
            print(f"  残り{target_completed - completed_trials}回の正常計算を継続します...")
    
    new_completed = completed_trials - initial_completed
    if completed_trials < target_completed:
        print(f"⚠️  警告: 最大試行回数（{max_iterations}）に達しました。完了trial数: {completed_trials}/{target_completed}（新規完了: {new_completed}/{n_trials}）")
    
    complete_count = completed_trials
    pruned_count = len([t for t in study.trials if t.state == TrialState.PRUNED])
    total_trials = len(study.trials)
    print(f"✓ 最適化完了（完了trial数: {completed_trials}/{target_completed}, 新規完了: {new_completed}/{n_trials}, 総試行数: {total_trials}, pruned: {pruned_count}）")
    
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
    
    # パラメータの取得とフォーマット
    rsi_base = best_trial.params.get('rsi_base', None)
    rsi_max = best_trial.params.get('rsi_max', None)
    bb_z_base = best_trial.params.get('bb_z_base', None)
    bb_z_max = best_trial.params.get('bb_z_max', None)
    
    rsi_base_str = f"{rsi_base:.2f}" if rsi_base is not None else "N/A"
    rsi_max_str = f"{rsi_max:.2f}" if rsi_max is not None else "N/A"
    rsi_width_str = f"{rsi_width:.2f}" if rsi_width is not None else "N/A"
    bb_z_base_str = f"{bb_z_base:.2f}" if bb_z_base is not None else "N/A"
    bb_z_max_str = f"{bb_z_max:.2f}" if bb_z_max is not None else "N/A"
    bb_z_width_str = f"{bb_z_width:.2f}" if bb_z_width is not None else "N/A"
    
    print(f"entry_score方向:")
    print(f"  RSI: {rsi_direction} (rsi_base={rsi_base_str}, rsi_max={rsi_max_str}, width={rsi_width_str})")
    print(f"  BB: {bb_direction} (bb_z_base={bb_z_base_str}, bb_z_max={bb_z_max_str}, width={bb_z_width_str})")
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
        rsi_min_width=10.0,  # 最小幅制約（緩和: 20.0 → 10.0）
        bb_z_min_width=0.5,  # 最小幅制約（緩和: 1.0 → 0.5）
    )
    
    # テストデータで評価
    # 注意: 24Mホライズンの場合、as_of_dateが現在日付に近いとtest期間のポートフォリオが
    # すべて「ホライズン未達」として除外される可能性がある
    # しかし、compare_lambda_penaltiesでは別途run_backtest_with_params_fileで評価するため、
    # ここでのtest評価は参考情報としてのみ使用される
    if not test_dates:
        # test_datesが空の場合（24Mホライズンで調整された場合など）、空の結果を返す
        print("⚠️  test_datesが空のため、test期間の評価をスキップします。")
        print("    compare_lambda_penaltiesで別途評価されます。")
        test_perf = {
            "mean_annual_excess_return_pct": 0.0,
            "median_annual_excess_return_pct": 0.0,
            "mean_annual_return_pct": 0.0,
            "median_annual_return_pct": 0.0,
            "cumulative_return_pct": 0.0,
            "mean_excess_return_pct": 0.0,
            "win_rate": 0.0,
            "num_portfolios": 0,
            "mean_holding_years": 0.0,
            "last_date": as_of_date if as_of_date else end_date,
        }
    else:
        try:
            test_perf = calculate_longterm_performance(
                test_dates,
                strategy_params,
                entry_params,
                cost_bps=cost_bps,
                n_jobs=backtest_n_jobs,
                features_dict=features_dict,
                prices_dict=prices_dict,
                horizon_months=horizon_months,
                require_full_horizon=True,  # ホライズン未達の期間を除外
                as_of_date=as_of_date,
                debug_rebalance_dates={"2023-01-31"} if "2023-01-31" in test_dates else None,  # デバッグ出力
            )
        except RuntimeError as e:
            # test期間の評価が失敗した場合（例：すべてホライズン未達）、
            # エラーメッセージを表示して空の結果を返す（最適化結果には影響しない）
            if "No performances were calculated" in str(e):
                print(f"⚠️  警告: test期間の評価に失敗しました（すべてホライズン未達の可能性）: {e}")
                print("    最適化結果は正常に完了しています。compare_lambda_penaltiesでは別途評価されます。")
                test_perf = {
                    "mean_annual_excess_return_pct": 0.0,
                    "median_annual_excess_return_pct": 0.0,
                    "mean_annual_return_pct": 0.0,
                    "median_annual_return_pct": 0.0,
                    "cumulative_return_pct": 0.0,
                    "mean_excess_return_pct": 0.0,
                    "win_rate": 0.0,
                    "num_portfolios": 0,
                    "mean_holding_years": 0.0,
                    "last_date": as_of_date if as_of_date else end_date,
                }
            else:
                # それ以外のRuntimeErrorはそのまま再発生
                raise
    
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
        # 重要: test_datesとtrain_datesを保存（compare_lambda_penaltiesで使用）
        "train_dates": train_dates,
        "test_dates": test_dates,
        "train_dates_first": train_dates[0] if train_dates else None,
        "train_dates_last": train_dates[-1] if train_dates else None,
        "test_dates_first": test_dates[0] if test_dates else None,
        "test_dates_last": test_dates[-1] if test_dates else None,
        "num_train_periods": len(train_dates),
        "num_test_periods": len(test_dates),
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
            "rsi_direction": best_params.get("rsi_direction", "unknown"),  # "momentum" or "reversal"
            "bb_z_base": best_params["bb_z_base"],
            "bb_z_max": best_params["bb_z_max"],
            "bb_direction": best_params.get("bb_direction", "unknown"),  # "momentum" or "reversal"
            "bb_weight": best_params["bb_weight"],
            "rsi_weight": 1.0 - best_params["bb_weight"],
            "rsi_min_width": 10.0,  # 固定値（最小幅制約、緩和済み）
            "bb_z_min_width": 0.5,  # 固定値（最小幅制約、緩和済み）
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
    parser.add_argument("--lambda-penalty", type=float, default=0.0, help="下振れ罰の係数λ（デフォルト: 0.0）")
    parser.add_argument("--horizon-months", type=int, default=24, help="投資ホライズン（月数、デフォルト: 24）")
    parser.add_argument("--strategy-mode", type=str, choices=["momentum", "reversal"], default=None, help="戦略モード（Noneの場合は自動判定）")
    parser.add_argument("--as-of-date", type=str, default=None, help="評価の打ち切り日（YYYY-MM-DD、Noneの場合はend_dateを使用）")
    parser.add_argument("--train-end-date", type=str, default=None, help="学習期間の終了日（YYYY-MM-DD、Noneの場合はtrain_ratioを使用）")
    parser.add_argument("--force-rebuild-cache", action="store_true", help="既存のキャッシュを無視して再構築する")
    parser.add_argument("--objective-type", type=str, choices=["mean", "median", "trimmed_mean"], default="mean",
                       help="目的関数の集計方法（mean: 平均、median: 中央値、trimmed_mean: 上下10%カット平均、デフォルト: mean）")
    
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
        save_params=args.save_params if hasattr(args, 'save_params') else None,
        params_id=args.params_id if hasattr(args, 'params_id') else None,
        version=args.version if hasattr(args, 'version') else None,
        horizon_months=args.horizon_months,
        strategy_mode=args.strategy_mode,
        as_of_date=args.as_of_date,
        train_end_date=args.train_end_date,
        lambda_penalty=args.lambda_penalty,
        force_rebuild_cache=args.force_rebuild_cache,
        objective_type=args.objective_type,
    )

