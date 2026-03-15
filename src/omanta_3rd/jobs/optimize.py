"""パラメータ最適化システム（Optuna使用、並列計算対応）"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace, fields
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
import optuna
from optuna.visualization import plot_optimization_history, plot_param_importances
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
import multiprocessing as mp
import sqlite3
from ..infra.db import connect_db
from ..jobs.longterm_run import (
    StrategyParams,
    build_features,
    select_portfolio,
    save_features,
    save_portfolio,
)
from ..backtest.performance import (
    calculate_portfolio_performance,
    save_performance_to_db,
)
from ..jobs.batch_longterm_run import get_monthly_rebalance_dates

# ---------------------------------------------------------------------------
# Re-exports from features/technicals.py（後方互換性維持）
# ---------------------------------------------------------------------------
from ..features.technicals import (  # noqa: F401
    EntryScoreParams,
    _entry_score_with_params,
    _calculate_entry_score_with_params,
)
from .progress_window import ProgressWindow, TKINTER_AVAILABLE  # noqa: F401


def _select_portfolio_with_params(
    feat: pd.DataFrame,
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
) -> pd.DataFrame:
    """
    パラメータ化されたポートフォリオ選択
    
    Args:
        feat: 特徴量DataFrame
        strategy_params: StrategyParams
        entry_params: EntryScoreParams
    
    Returns:
        選択されたポートフォリオ
    """
    from ..jobs.longterm_run import (
        _pct_rank,
        _log_safe,
        PARAMS as DEFAULT_PARAMS,
    )
    
    # entry_scoreを計算（パラメータ化版）
    # 重要: 最適化ではtrialごとに異なるentry_paramsが使用されるため、
    # キャッシュされたentry_scoreは使用しない（常に再計算）
    # FeatureCacheではentry_scoreを削除しているため、常に再計算される
    print(f"        [_select_portfolio] entry_scoreを計算します（entry_paramsに基づく）")
    import sys
    sys.stdout.flush()
    
    # 価格データを取得
    price_date = feat["as_of_date"].iloc[0]
    with connect_db() as conn:
        prices_win = pd.read_sql_query(
            """
            SELECT code, date, adj_close
            FROM prices_daily
            WHERE date <= ?
            ORDER BY code, date
            """,
            conn,
            params=(price_date,),
        )
    
    feat = _calculate_entry_score_with_params(feat, prices_win, entry_params)
    
    # フィルタリング
    # 重要: featを破壊的に変更しないため、必ずcopyを作成
    # これにより、trial間でfeatが汚染されることを防ぐ
    df = feat.copy()
    
    # Liquidity filter
    if strategy_params.liquidity_quantile_cut > 0:
        q = df["liquidity_60d"].quantile(strategy_params.liquidity_quantile_cut)
        df = df[df["liquidity_60d"] >= q]
    
    # ROE filter
    df = df[df["roe"] >= strategy_params.roe_min]
    
    if df.empty:
        return pd.DataFrame()
    
    # Value score
    df["forward_per_pct"] = df.groupby("sector33")["forward_per"].transform(
        lambda s: _pct_rank(s, ascending=True)
    )
    df["pbr_pct"] = df.groupby("sector33")["pbr"].transform(
        lambda s: _pct_rank(s, ascending=True)
    )
    df["value_score"] = (
        strategy_params.w_forward_per * (1.0 - df["forward_per_pct"])
        + strategy_params.w_pbr * (1.0 - df["pbr_pct"])
    )
    
    # Size score
    df["log_mcap"] = df["market_cap"].apply(_log_safe)
    df["size_score"] = _pct_rank(df["log_mcap"], ascending=True)
    
    # Quality score
    df["roe_score"] = _pct_rank(df["roe"], ascending=True)
    df["quality_score"] = df["roe_score"]
    
    # Growth score
    df["op_growth_score"] = _pct_rank(df["op_growth"], ascending=True).fillna(0.5)
    df["profit_growth_score"] = _pct_rank(df["profit_growth"], ascending=True).fillna(0.5)
    df["op_trend_score"] = _pct_rank(df["op_trend"], ascending=True).fillna(0.5)
    df["growth_score"] = (
        0.4 * df["op_growth_score"]
        + 0.4 * df["profit_growth_score"]
        + 0.2 * df["op_trend_score"]
    )
    
    # Record-high score
    df["record_high_score"] = df["record_high_forecast_flag"].astype(float)
    
    # Fill NaN
    df["value_score"] = df["value_score"].fillna(0.5)
    df["growth_score"] = df["growth_score"].fillna(0.5)
    df["size_score"] = df["size_score"].fillna(0.5)
    df["quality_score"] = df["quality_score"].fillna(0.0)
    df["record_high_score"] = df["record_high_score"].fillna(0.0)
    
    # Core score
    df["core_score"] = (
        strategy_params.w_quality * df["quality_score"]
        + strategy_params.w_value * df["value_score"]
        + strategy_params.w_growth * df["growth_score"]
        + strategy_params.w_record_high * df["record_high_score"]
        + strategy_params.w_size * df["size_score"]
    )
    df["core_score"] = df["core_score"].fillna(0.0)
    
    # Pool selection
    pool = df.nlargest(strategy_params.pool_size, "core_score")
    
    # Final selection with entry_score
    if strategy_params.use_entry_score:
        pool = pool.sort_values(
            ["entry_score", "core_score"], ascending=[False, False]
        )
    else:
        pool = pool.sort_values("core_score", ascending=False)
    
    # Sector cap
    selected = []
    sector_counts = {}
    for _, row in pool.iterrows():
        sector = row["sector33"]
        if sector_counts.get(sector, 0) < strategy_params.sector_cap:
            selected.append(row)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            if len(selected) >= strategy_params.target_max:
                break
    
    if len(selected) < strategy_params.target_min:
        # セクター制限を緩和
        selected_indices = [s.name if hasattr(s, 'name') else s.index[0] if hasattr(s, 'index') else None for s in selected]
        selected_indices = [idx for idx in selected_indices if idx is not None]
        remaining = pool[~pool.index.isin(selected_indices)]
        for _, row in remaining.iterrows():
            selected.append(row)
            if len(selected) >= strategy_params.target_min:
                break
    
    # DataFrameに変換（selectedがSeriesのリストの場合）
    if selected and isinstance(selected[0], pd.Series):
        sel_df = pd.DataFrame(selected)
    else:
        sel_df = pd.DataFrame(selected)
    if sel_df.empty:
        return pd.DataFrame()
    
    # Weight calculation: 等ウェイト（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）
    n = len(sel_df)
    sel_df["weight"] = 1.0 / n
    
    # reasonカラムが存在しない場合は作成
    if "reason" not in sel_df.columns:
        sel_df["reason"] = ""
    
    sel_df = sel_df[["code", "weight", "core_score", "entry_score", "reason"]].copy()
    sel_df.insert(0, "rebalance_date", feat["as_of_date"].iloc[0])
    
    return sel_df


def _run_single_backtest(
    rebalance_date: str,
    strategy_params_dict: dict,
    entry_params_dict: dict,
    as_of_date: Optional[str] = None,
    save_portfolio_to_db: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    単一のリバランス日に対するバックテスト実行（並列化用、最適化版）
    
    Args:
        rebalance_date: リバランス日
        strategy_params_dict: StrategyParamsを辞書化したもの
        entry_params_dict: EntryScoreParamsを辞書化したもの
        as_of_date: 評価日
        save_portfolio_to_db: ポートフォリオをDBに保存するか（デフォルト: False、後で一括保存）
    
    Returns:
        パフォーマンス結果（エラー時はNone）
    """
    try:
        # 辞書からdataclassに復元
        strategy_params = StrategyParams(**strategy_params_dict)
        entry_params = EntryScoreParams(**entry_params_dict)
        
        # 1) feat を必ず作る（read_only失敗ならread_writeへ）
        try:
            with connect_db(read_only=True) as conn:
                feat = build_features(conn, rebalance_date, strategy_params=strategy_params, entry_params=entry_params)
        except sqlite3.OperationalError as e:
            # 読み取り専用エラーの場合は通常の接続を使用
            if "readonly" in str(e).lower() or "read-only" in str(e).lower():
                with connect_db(read_only=False) as conn:
                    feat = build_features(conn, rebalance_date, strategy_params=strategy_params, entry_params=entry_params)
            else:
                raise
        
        # 2) ここからは共通処理（exceptの外！）
        if feat is None or feat.empty:
            return None
        
        # ポートフォリオを選択（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）
        portfolio = _select_portfolio_with_params(feat, strategy_params, entry_params)
        
        if portfolio is None or portfolio.empty:
            return None
        
        # 3) perf がDBのportfolioを読むなら、保存してから計算が必要
        if save_portfolio_to_db:
            with connect_db(read_only=False) as conn:
                save_portfolio(conn, portfolio)
        
        # パフォーマンスを計算（DBからポートフォリオを読む設計）
        perf = calculate_portfolio_performance(rebalance_date, as_of_date)
        
        # ポートフォリオ情報を結果に含める（後で一括保存するため）
        if isinstance(perf, dict) and "error" not in perf:
            perf["_portfolio"] = portfolio.to_dict("records")  # 一時的に保存
            return perf
        return None
    except Exception as e:
        print(f"エラー ({rebalance_date}): {e}")
        import traceback
        traceback.print_exc()
        return None
def _calculate_performance_single(
    rebalance_date: str,
    as_of_date: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    単一のリバランス日に対するパフォーマンス計算（並列化用）
    
    Args:
        rebalance_date: リバランス日
        as_of_date: 評価日
    
    Returns:
        パフォーマンス結果（エラー時はNone）
    """
    try:
        perf = calculate_portfolio_performance(rebalance_date, as_of_date)
        if perf is not None and isinstance(perf, dict) and "error" not in perf:
            return perf
    except Exception as e:
        print(f"パフォーマンス計算エラー ({rebalance_date}): {e}")
    return None


def _select_portfolio_for_rebalance_date(
    rebalance_date: str,
    strategy_params_dict: dict,
    entry_params_dict: dict,
) -> Optional[pd.DataFrame]:
    """
    単一のリバランス日に対するポートフォリオ選定のみ（並列化用）
    
    【注意】この関数は「ポートフォリオ選定のみ」を行います。パフォーマンス計算は行いません。
    長期保有型と月次リバランス型の両方で使用可能です。
    違いは「パフォーマンス計算方法」のみです（長期保有型：固定ホライズン評価、月次リバランス型：月次リターン系列）。
    
    Args:
        rebalance_date: リバランス日
        strategy_params_dict: StrategyParamsを辞書化したもの
        entry_params_dict: EntryScoreParamsを辞書化したもの
    
    Returns:
        ポートフォリオDataFrame（エラー時はNone）
    """
    try:
        # 辞書からdataclassに復元
        strategy_params = StrategyParams(**strategy_params_dict)
        entry_params = EntryScoreParams(**entry_params_dict)
        
        # feat を必ず作る（read_only失敗ならread_writeへ）
        try:
            with connect_db(read_only=True) as conn:
                feat = build_features(conn, rebalance_date, strategy_params=strategy_params, entry_params=entry_params)
        except sqlite3.OperationalError as e:
            if "readonly" in str(e).lower() or "read-only" in str(e).lower():
                with connect_db(read_only=False) as conn:
                    feat = build_features(conn, rebalance_date, strategy_params=strategy_params, entry_params=entry_params)
            else:
                raise
        
        if feat is None or feat.empty:
            return None
        
        # ポートフォリオを選択（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）
        portfolio = _select_portfolio_with_params(feat, strategy_params, entry_params)
        
        if portfolio is None or portfolio.empty:
            return None
        
        return portfolio
    except Exception as e:
        print(f"エラー ({rebalance_date}): {e}")
        import traceback
        traceback.print_exc()
        return None


def run_backtest_for_optimization(
    rebalance_dates: List[str],
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
    as_of_date: Optional[str] = None,
    n_jobs: int = -1,
) -> Dict[str, float]:
    """
    最適化用のバックテスト実行（並列計算対応、B-2方式）
    
    設計: 並列ワーカーは「ポートフォリオ選定だけ」を返し、
          保存後にメインでperformanceを計算する
    
    Args:
        rebalance_dates: リバランス日のリスト
        strategy_params: StrategyParams
        entry_params: EntryScoreParams
        as_of_date: 評価日（Noneの場合は最新）
        n_jobs: 並列実行数（-1でCPU数、1で逐次実行）
    
    Returns:
        パフォーマンス指標の辞書
    """
    # dataclassを辞書に変換（pickle可能にするため）
    strategy_params_dict = {
        field.name: getattr(strategy_params, field.name)
        for field in fields(StrategyParams)
    }
    entry_params_dict = {
        field.name: getattr(entry_params, field.name)
        for field in fields(EntryScoreParams)
    }
    
    # 並列実行数の決定（タスク数とCPU数のバランスを考慮）
    if n_jobs == -1:
        # タスク数が少ない場合は、タスク数に合わせる
        # タスク数が多い場合は、CPU数を上限とする
        n_jobs = min(len(rebalance_dates), mp.cpu_count())
    elif n_jobs <= 0:
        n_jobs = 1
    
    portfolios = {}  # {rebalance_date: portfolio_df}
    
    # 並列実行: ポートフォリオ選定のみ
    if n_jobs > 1 and len(rebalance_dates) > 1:
        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            futures = {
                executor.submit(
                    _select_portfolio_for_rebalance_date,
                    rebalance_date,
                    strategy_params_dict,
                    entry_params_dict,
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
        for rebalance_date in rebalance_dates:
            portfolio = _select_portfolio_for_rebalance_date(
                rebalance_date,
                strategy_params_dict,
                entry_params_dict,
            )
            if portfolio is not None and not portfolio.empty:
                portfolios[rebalance_date] = portfolio
    
    # デバッグ: 結果が空なら例外を投げる（ペナルティ固定を防ぐ）
    if not portfolios:
        raise RuntimeError(
            f"No portfolios were generated for any rebalance dates. "
            f"Check worker errors, feature building, or portfolio selection logic."
        )
    
    # ポートフォリオを一括保存
    with connect_db() as conn:
        for rebalance_date, portfolio_df in portfolios.items():
            save_portfolio(conn, portfolio_df)
    
    # パフォーマンスを計算（保存後に実行、並列化可能）
    results = []
    if n_jobs > 1 and len(portfolios) > 1:
        # パフォーマンス計算も並列化（読み取り専用なので安全）
        with ProcessPoolExecutor(max_workers=min(n_jobs, len(portfolios))) as executor:
            futures = {
                executor.submit(_calculate_performance_single, rebalance_date, as_of_date): rebalance_date
                for rebalance_date in portfolios.keys()
            }
            for future in as_completed(futures):
                perf = future.result()
                if perf is not None:
                    results.append(perf)
    else:
        # 逐次実行
        for rebalance_date in portfolios.keys():
            perf = calculate_portfolio_performance(rebalance_date, as_of_date)
            if perf is not None and isinstance(perf, dict) and "error" not in perf:
                results.append(perf)
    
    if not results:
        raise RuntimeError(
            f"No performance results were calculated. "
            f"Check calculate_portfolio_performance() logic."
        )
    
    # パフォーマンス指標を計算
    excess_returns = [
        r.get("topix_comparison", {}).get("excess_return_pct")
        for r in results
        if r.get("topix_comparison", {}).get("excess_return_pct") is not None
    ]
    
    returns = [
        r.get("total_return_pct")
        for r in results
        if r.get("total_return_pct") is not None
    ]
    
    if not excess_returns:
        raise RuntimeError(
            f"No excess returns were calculated. "
            f"Check portfolio performance calculation."
        )
    
    mean_excess_return = np.mean(excess_returns)
    mean_return = np.mean(returns) if returns else 0.0
    win_rate = sum(1 for x in excess_returns if x > 0) / len(excess_returns)
    
    # 簡易シャープレシオ（超過リターンの平均/標準偏差）
    if len(excess_returns) > 1:
        sharpe_ratio = mean_excess_return / (np.std(excess_returns) + 1e-6)
    else:
        sharpe_ratio = 0.0
    
    return {
        "mean_excess_return": mean_excess_return,
        "mean_return": mean_return,
        "win_rate": win_rate,
        "sharpe_ratio": sharpe_ratio,
        "num_portfolios": len(results),
    }


def objective(
    trial: optuna.Trial,
    rebalance_dates: List[str],
    as_of_date: Optional[str],
    n_jobs: int = -1,
) -> float:
    """
    Optunaの目的関数
    
    Args:
        trial: OptunaのTrialオブジェクト
        rebalance_dates: リバランス日のリスト
        as_of_date: 評価日
        n_jobs: 並列実行数（-1でCPU数）
    
    Returns:
        最適化対象の値（平均超過リターン）
    """
    # StrategyParamsのパラメータ（前回の最適化結果を踏まえて範囲を調整）
    # 前回の最適値: w_quality=0.2245, w_value=0.3008, w_growth=0.1006, w_record_high=0.0609, w_size=0.1604
    w_quality = trial.suggest_float("w_quality", 0.15, 0.35)
    w_value = trial.suggest_float("w_value", 0.20, 0.40)
    w_growth = trial.suggest_float("w_growth", 0.05, 0.20)
    w_record_high = trial.suggest_float("w_record_high", 0.03, 0.15)
    w_size = trial.suggest_float("w_size", 0.10, 0.25)
    
    # 正規化（合計が1になるように）
    total = w_quality + w_value + w_growth + w_record_high + w_size
    w_quality /= total
    w_value /= total
    w_growth /= total
    w_record_high /= total
    w_size /= total
    
    # 前回の最適値: w_forward_per=0.4825
    w_forward_per = trial.suggest_float("w_forward_per", 0.35, 0.65)
    w_pbr = 1.0 - w_forward_per
    
    # 前回の最適値: roe_min=0.0711, liquidity_quantile_cut=0.2642
    roe_min = trial.suggest_float("roe_min", 0.05, 0.12)
    liquidity_quantile_cut = trial.suggest_float("liquidity_quantile_cut", 0.15, 0.35)
    
    # StrategyParamsはfrozenなので、replaceを使用
    # ポートフォリオ銘柄数を12に設定
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
    
    # EntryScoreParamsのパラメータ（順張り向けに調整）
    # 順張り: RSIが高いほど、BB Z-scoreが高いほど高スコア
    # BB Z-scoreはボリンジャーバンドのシグマ（標準偏差の倍数）を表す
    # Z-score = 0: 移動平均、Z-score = ±1: ±1シグマ、Z-score = ±2: ±2シグマ
    # 前回の最適値: rsi_base=44.6, rsi_max=78.7, bb_z_base=-1.41, bb_z_max=2.50, bb_weight=0.6233
    rsi_base = trial.suggest_float("rsi_base", 35.0, 60.0)  # 基準値: 35-60（前回44.6を中心に）
    # rsi_maxはrsi_baseより大きい必要がある（制約付きサンプリング）
    rsi_max = trial.suggest_float("rsi_max", max(70.0, rsi_base + 5.0), 85.0)  # 上限: rsi_base+5以上、85以下（前回78.7を中心に）
    bb_z_base = trial.suggest_float("bb_z_base", -2.0, 0.0)  # 基準値: -2～0シグマ（前回-1.41を中心に）
    # bb_z_maxはbb_z_baseより大きい必要がある（制約付きサンプリング）
    bb_z_max = trial.suggest_float("bb_z_max", max(2.0, bb_z_base + 0.5), 3.5)  # 上限: bb_z_base+0.5以上、3.5以下（前回2.50を中心に）
    bb_weight = trial.suggest_float("bb_weight", 0.45, 0.75)  # 前回0.6233を中心に
    rsi_weight = 1.0 - bb_weight
    
    entry_params = EntryScoreParams(
        rsi_base=rsi_base,
        rsi_max=rsi_max,
        bb_z_base=bb_z_base,
        bb_z_max=bb_z_max,
        bb_weight=bb_weight,
        rsi_weight=rsi_weight,
    )
    
    # バックテスト実行（並列計算）
    perf = run_backtest_for_optimization(
        rebalance_dates, strategy_params, entry_params, as_of_date, n_jobs=n_jobs
    )
    
    # 目的関数: 平均超過リターン（勝率とシャープレシオも考慮）
    objective_value = (
        perf["mean_excess_return"] * 0.7
        + perf["win_rate"] * 10.0 * 0.2  # 勝率を10倍してスケール調整
        + perf["sharpe_ratio"] * 0.1
    )
    
    # デバッグ用ログ出力
    print(
        f"[Trial {trial.number}] "
        f"objective={objective_value:.4f}, "
        f"excess_return={perf['mean_excess_return']:.4f}, "
        f"win_rate={perf['win_rate']:.4f}, "
        f"sharpe={perf['sharpe_ratio']:.4f}, "
        f"num_portfolios={perf.get('num_portfolios', 0)}"
    )
    
    return objective_value


def main(
    start_date: str,
    end_date: str,
    n_trials: int = 50,
    as_of_date: Optional[str] = None,
    study_name: Optional[str] = None,
    n_jobs: int = -1,
    show_progress_window: bool = True,
):
    """
    メイン処理
    
    Args:
        start_date: 開始日
        end_date: 終了日
        n_trials: 試行回数
        as_of_date: 評価日
        study_name: スタディ名
    """
    print("=" * 80)
    print("パラメータ最適化システム（並列計算対応）")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"試行回数: {n_trials}")
    print(f"評価日: {as_of_date or '最新'}")
    if n_jobs == -1:
        print(f"並列実行数: {mp.cpu_count()} (CPU数、ポートフォリオ保存は一括化)")
    else:
        print(f"並列実行数: {n_jobs}")
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
    
    # Optunaスタディを作成
    if study_name is None:
        study_name = f"optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    study = optuna.create_study(
        direction="maximize",
        study_name=study_name,
        storage=f"sqlite:///optuna_{study_name}.db",
        load_if_exists=True,
    )
    
    # 進捗ウィンドウを作成
    progress_window = None
    if show_progress_window and TKINTER_AVAILABLE:
        progress_window = ProgressWindow(n_trials)
        progress_window.run()
        print("進捗ウィンドウを表示しました")
    
    # コールバック関数
    def callback(study: optuna.Study, trial: optuna.Trial):
        """最適化の進捗を更新"""
        if progress_window:
            # 試行の値（完了している場合）
            current_value = trial.value if trial.value is not None else None
            # 最良値（堅牢化: ValueErrorをキャッチ）
            best_value = None
            try:
                best_value = study.best_value
            except ValueError:
                # 完了trialが無い場合
                if len(study.trials) > 0:
                    completed_trials = [
                        t for t in study.trials 
                        if t.state == optuna.trial.TrialState.COMPLETE
                    ]
                    if completed_trials:
                        best_trial = max(
                            completed_trials,
                            key=lambda t: t.value if t.value is not None else float('-inf')
                        )
                        best_value = best_trial.value if best_trial.value is not None else None
            
            params = trial.params if hasattr(trial, 'params') else None
            
            # デバッグ用ログ
            try:
                study_best = study.best_value
            except ValueError:
                study_best = 'N/A'
            
            print(
                f"[Callback Trial {trial.number}] "
                f"current_value={current_value}, "
                f"best_value={best_value}, "
                f"study.best_value={study_best}"
            )
            
            # 最良値で更新
            if best_value is not None:
                progress_window.update(trial.number + 1, best_value, params)
            elif current_value is not None:
                # 試行が完了しているが最良値がまだない場合
                progress_window.update(trial.number + 1, current_value, params)
    
    # 最適化実行（並列化）
    print("最適化を開始します...")
    # Optunaの並列化はsamplerで制御（TPEは並列化に対応）
    # 各試行内でバックテストを並列化するため、Optunaの試行は逐次実行
    study.optimize(
        lambda trial: objective(trial, rebalance_dates, as_of_date, n_jobs),
        n_trials=n_trials,
        show_progress_bar=True,
        n_jobs=1,  # Optunaの試行は逐次実行（各試行内でバックテストを並列化）
        callbacks=[callback] if progress_window else None,
    )
    
    # 進捗ウィンドウを閉じる
    if progress_window:
        progress_window.close()
    
    # 結果表示
    print()
    print("=" * 80)
    print("【最適化結果】")
    print("=" * 80)
    print(f"最良試行: {study.best_trial.number}")
    print(f"最良値: {study.best_value:.4f}")
    print()
    print("最良パラメータ:")
    for key, value in study.best_params.items():
        print(f"  {key}: {value:.4f}")
    print()
    
    # 結果をJSONに保存
    # 注意: study.best_paramsは正規化前の値なので、正規化後の値を計算
    best_params_raw = study.best_params.copy()
    
    # Core Score重みの正規化
    w_quality = best_params_raw.get("w_quality", 0.0)
    w_value = best_params_raw.get("w_value", 0.0)
    w_growth = best_params_raw.get("w_growth", 0.0)
    w_record_high = best_params_raw.get("w_record_high", 0.0)
    w_size = best_params_raw.get("w_size", 0.0)
    total = w_quality + w_value + w_growth + w_record_high + w_size
    if total > 0:
        w_quality_norm = w_quality / total
        w_value_norm = w_value / total
        w_growth_norm = w_growth / total
        w_record_high_norm = w_record_high / total
        w_size_norm = w_size / total
    else:
        w_quality_norm = w_quality
        w_value_norm = w_value
        w_growth_norm = w_growth
        w_record_high_norm = w_record_high
        w_size_norm = w_size
    
    # 正規化後のパラメータを作成
    best_params_normalized = best_params_raw.copy()
    best_params_normalized["w_quality"] = w_quality_norm
    best_params_normalized["w_value"] = w_value_norm
    best_params_normalized["w_growth"] = w_growth_norm
    best_params_normalized["w_record_high"] = w_record_high_norm
    best_params_normalized["w_size"] = w_size_norm
    
    result_file = f"optimization_result_{study_name}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "best_value": study.best_value,
                "best_params": best_params_normalized,  # 正規化後の値を保存
                "best_params_raw": best_params_raw,  # 正規化前の値も保存（参考用）
                "n_trials": n_trials,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"結果を {result_file} に保存しました")
    
    # 可視化（オプション、plotlyが必要）
    try:
        import plotly
        fig1 = plot_optimization_history(study)
        fig1.write_image(f"optimization_history_{study_name}.png")
        print(f"最適化履歴を optimization_history_{study_name}.png に保存しました")
        
        fig2 = plot_param_importances(study)
        fig2.write_image(f"param_importances_{study_name}.png")
        print(f"パラメータ重要度を param_importances_{study_name}.png に保存しました")
    except ImportError:
        print("可視化にはplotlyが必要です。インストールする場合は: pip install plotly kaleido")
    except Exception as e:
        print(f"可視化の保存でエラー: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="パラメータ最適化")
    parser.add_argument("--start", type=str, required=True, help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, required=True, help="終了日（YYYY-MM-DD）")
    parser.add_argument("--n-trials", type=int, default=50, help="試行回数")
    parser.add_argument("--as-of-date", type=str, default=None, help="評価日（YYYY-MM-DD）")
    parser.add_argument("--study-name", type=str, default=None, help="スタディ名")
    parser.add_argument("--n-jobs", type=int, default=-1, help="並列実行数（-1でCPU数、1で逐次実行）")
    parser.add_argument("--no-progress-window", action="store_true", help="進捗ウィンドウを表示しない")
    
    args = parser.parse_args()
    
    main(
        start_date=args.start,
        end_date=args.end,
        n_trials=args.n_trials,
        as_of_date=args.as_of_date,
        study_name=args.study_name,
        n_jobs=args.n_jobs,
        show_progress_window=not args.no_progress_window,
    )

