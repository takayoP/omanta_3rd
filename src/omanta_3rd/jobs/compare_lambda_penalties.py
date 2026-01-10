"""
下振れ罰係数λの比較スクリプト

複数のλ値で最適化を実行し、結果を比較します：
- λ=0.00（現状：下振れ罰なし）
- λ=0.05（メイン候補）
- λ=0.03（追加候補）
- λ=0.08（追加候補）

同じ条件（固定ホライズン、同じtrain/val/holdout）で並走させて、
平均超過、P10、勝率、切替回数を比較します。

使用方法:
    python -m omanta_3rd.jobs.compare_lambda_penalties --start 2020-01-01 --end 2025-12-31 --params-id operational_24M --n-trials 200
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd

from ..infra.db import connect_db
from ..jobs.batch_longterm_run import get_monthly_rebalance_dates
from ..jobs.batch_longterm_run_with_regime import run_monthly_portfolio_with_regime
from ..backtest.performance_from_dataframe import calculate_portfolio_performance_from_dataframe
from ..config.settings import PROJECT_ROOT
from ..config.params_registry import get_registry_entry, load_params_by_id_longterm
from ..jobs.longterm_run import _snap_price_date
from ..jobs.params_utils import normalize_params
from ..jobs.optimize_longterm import main as optimize_longterm_main
from ..jobs.reoptimize_all_candidates import save_params_file, determine_strategy_mode
from dateutil.relativedelta import relativedelta


def calculate_annualized_return_from_period(
    total_return: float,
    start_date: str,
    end_date: str,
) -> float:
    """期間リターンから年率リターンを計算"""
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    days_diff = (end_dt - start_dt).days
    if days_diff <= 0:
        return 0.0
    
    years = days_diff / 365.25
    if years <= 0:
        return 0.0
    
    if total_return <= -1.0:
        return -1.0
    
    annualized = ((1.0 + total_return) ** (1.0 / years)) - 1.0
    return annualized


def calculate_percentile(returns: List[float], percentile: float) -> float:
    """パーセンタイルを計算"""
    import numpy as np
    if not returns:
        return 0.0
    return float(np.percentile(returns, percentile))


def count_switches_from_performances(performances: List[Dict[str, Any]]) -> int:
    """
    切替回数をカウント（パフォーマンス結果から）
    
    Args:
        performances: パフォーマンスのリスト（rebalance_date順にソート済み）
    
    Returns:
        切替回数
    """
    if len(performances) < 2:
        return 0
    
    switch_count = 0
    prev_params_id = None
    
    for perf in performances:
        current_params_id = perf.get("params_id")
        if prev_params_id is not None and current_params_id != prev_params_id:
            switch_count += 1
        prev_params_id = current_params_id
    
    return switch_count


def run_backtest_with_params_file(
    params_file_path: Path,
    start_date: str,
    end_date: str,
    as_of_date: str,
    require_full_horizon: bool = True,
    rebalance_dates: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    パラメータファイルを使ってバックテストを実行
    
    Args:
        params_file_path: パラメータファイルのパス
        start_date: 開始日
        end_date: 終了日
        as_of_date: 評価日
        require_full_horizon: 満了窓のみ集計するか
    
    Returns:
        バックテスト結果（平均超過、P10、勝率、切替回数）
    """
    # パラメータファイルを読み込む
    with open(params_file_path, 'r', encoding='utf-8') as f:
        params_data = json.load(f)
    
    # metadataからparams_idとhorizon_monthsを取得（新しい形式）
    metadata = params_data.get("metadata", {})
    params_id = metadata.get("params_id") or params_data.get("params_id")  # 後方互換性のため両方をチェック
    base_params_id = metadata.get("base_params_id") or params_data.get("base_params_id")  # 元のparams_id
    horizon_months = metadata.get("horizon_months") or params_data.get("horizon_months")  # 後方互換性のため両方をチェック
    
    if not horizon_months:
        return {"error": "horizon_monthsがパラメータファイルに見つかりません"}
    
    # params_idがない場合は、ファイル名から推測を試みる
    # 注意: ファイル名は params_operational_24M_lambda0.05_20260110.json のような形式
    if not params_id:
        filename = params_file_path.stem
        # lambda の部分を除去して元のparams_idを推測
        if "_lambda" in filename:
            params_id_from_file = filename.split("_lambda")[0].replace("params_", "")
        else:
            params_id_from_file = filename.replace("params_", "").split("_")[0]
        
        if "operational_24M" in params_id_from_file:
            base_params_id = "operational_24M"
            params_id = params_id_from_file
        elif "12M_momentum" in params_id_from_file:
            base_params_id = "12M_momentum"
            params_id = params_id_from_file
        elif "12M_reversal" in params_id_from_file:
            base_params_id = "12M_reversal"
            params_id = params_id_from_file
        else:
            # ファイル名から直接推測を試みる（最後の手段）
            if "operational_24M" in filename:
                base_params_id = "operational_24M"
                params_id = "operational_24M"
            elif "12M_momentum" in filename:
                base_params_id = "12M_momentum"
                params_id = "12M_momentum"
            elif "12M_reversal" in filename:
                base_params_id = "12M_reversal"
                params_id = "12M_reversal"
            else:
                return {"error": f"params_idがパラメータファイルに見つかりません（ファイル名: {filename}）"}
    
    # base_params_idがない場合は、params_idから推測
    if not base_params_id:
        if "_lambda" in params_id:
            base_params_id_candidate = params_id.split("_lambda")[0]
            # 元のparams_idに変換
            if "operational_24M" in base_params_id_candidate:
                base_params_id = "operational_24M"
            elif "12M_momentum" in base_params_id_candidate:
                base_params_id = "12M_momentum"
            elif "12M_reversal" in base_params_id_candidate:
                base_params_id = "12M_reversal"
            else:
                base_params_id = base_params_id_candidate
        else:
            base_params_id = params_id
    
    # パラメータファイルから直接パラメータを読み込む（最適化されたパラメータを使用）
    # 注意: registryには lambda を含まない元のparams_idが登録されているが、
    #       最適化されたパラメータはパラメータファイルに保存されているため、パラメータファイルから読み込む
    params = params_data.get("params", {})
    if not params:
        return {"error": "パラメータがパラメータファイルに見つかりません"}
    
    # StrategyParamsとEntryScoreParamsを構築（パラメータファイルから直接読み込む）
    from ..jobs.longterm_run import StrategyParams
    from ..jobs.optimize import EntryScoreParams
    
    strategy_params = StrategyParams(
        target_min=12,
        target_max=12,
        w_quality=params.get("w_quality", 0.0),
        w_value=params.get("w_value", 0.0),
        w_growth=params.get("w_growth", 0.0),
        w_record_high=params.get("w_record_high", 0.0),
        w_size=params.get("w_size", 0.0),
        w_forward_per=params.get("w_forward_per", 0.0),
        w_pbr=params.get("w_pbr", 0.0),
        roe_min=params.get("roe_min", 0.0),
        liquidity_quantile_cut=params.get("liquidity_quantile_cut", 0.1),
    )
    
    entry_params = EntryScoreParams(
        rsi_base=params.get("rsi_base", 50.0),
        rsi_max=params.get("rsi_max", 70.0),
        bb_z_base=params.get("bb_z_base", 0.0),
        bb_z_max=params.get("bb_z_max", 1.0),
        bb_weight=params.get("bb_weight", 0.5),
        rsi_weight=1.0 - params.get("bb_weight", 0.5),
        rsi_min_width=params.get("rsi_min_width", 20.0),
        bb_z_min_width=params.get("bb_z_min_width", 1.0),
    )
    
    # リバランス日を取得（固定ホライズン評価）
    if rebalance_dates is None:
        all_dates = get_monthly_rebalance_dates(start_date, end_date)
    else:
        # 指定されたリバランス日を使用（start_dateとend_dateでフィルタリング）
        all_dates = [d for d in rebalance_dates if start_date <= d <= end_date]
    
    # 固定ホライズン制約でフィルタリング
    valid_dates = []
    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    for rebalance_date in all_dates:
        rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
        eval_end_dt = rebalance_dt + relativedelta(months=horizon_months)
        if not require_full_horizon or eval_end_dt <= as_of_dt:
            valid_dates.append(rebalance_date)
    
    # パラメータファイルから直接読み込んだパラメータを使用してポートフォリオを作成
    from ..jobs.longterm_run import build_features, select_portfolio
    from ..infra.db import connect_db
    
    # 各リバランス日でポートフォリオを作成（パラメータファイルから直接読み込んだパラメータを使用）
    performances = []
    for rebalance_date in valid_dates:
        try:
            with connect_db() as conn:
                # 特徴量を構築
                feat = build_features(conn, rebalance_date, strategy_params=strategy_params, entry_params=entry_params)
                
                if feat.empty:
                    print(f"      [run_backtest_with_params_file] ⚠️  {rebalance_date}: 特徴量が空です")
                    continue
                
                # ポートフォリオを選択
                portfolio = select_portfolio(feat, strategy_params=strategy_params)
                
                if portfolio.empty:
                    print(f"      [run_backtest_with_params_file] ⚠️  {rebalance_date}: ポートフォリオが空です")
                    continue
                
                result = {
                    "portfolio_created": True,
                    "portfolio": portfolio,
                    "horizon_months": horizon_months,
                }
        except Exception as e:
            print(f"      [run_backtest_with_params_file] ❌ {rebalance_date}: エラー - {e}")
            import traceback
            traceback.print_exc()
            continue
        
        if not result.get("portfolio_created") or "portfolio" not in result:
            continue
        
        # 満了窓チェック
        horizon_months_actual = result.get("horizon_months")
        if horizon_months_actual and require_full_horizon:
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_end_dt = rebalance_dt + relativedelta(months=horizon_months_actual)
            if eval_end_dt > as_of_dt:
                continue
        
        # eval_end = rebalance_date + horizon_months（ホライズン固定）
        rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
        eval_end_raw = rebalance_dt + relativedelta(months=horizon_months_actual or horizon_months)
        eval_end_raw_str = eval_end_raw.strftime("%Y-%m-%d")
        
        if require_full_horizon:
            if eval_end_raw > as_of_dt:
                continue
        
        # eval_endを営業日にスナップ（固定ホライズンを守るため）
        # 重要: スナップ関数の引数はeval_end_raw_strである必要がある（固定ホライズンを守るため）
        with connect_db() as conn:
            eval_end_snapped = _snap_price_date(conn, min(eval_end_raw_str, as_of_date))
            
            # スナップ差分が大きい場合（データ欠損で数週間〜数ヶ月戻るケース）は除外（ChatGPT推奨）
            eval_end_raw_dt = datetime.strptime(eval_end_raw_str, "%Y-%m-%d")
            eval_end_snapped_dt = datetime.strptime(eval_end_snapped, "%Y-%m-%d")
            snap_diff_days = (eval_end_raw_dt - eval_end_snapped_dt).days
            
            if snap_diff_days > 7:  # 1週間以上のズレは除外
                print(f"      [run_backtest_with_params_file] ⚠️  {rebalance_date}のeval_endスナップ差分が大きい（{snap_diff_days}日）のため除外: {eval_end_raw_str} → {eval_end_snapped}")
                continue
            
            # require_full_horizon=Trueの場合は、固定ホライズン評価を保証するためのアサーション
            if require_full_horizon:
                # require_full_horizon=Trueなら、eval_end_raw <= as_of_dateが保証されている
                # また、スナップ差分が小さい（7日以内）ことも確認済み
                if snap_diff_days > 0:
                    print(f"      [run_backtest_with_params_file] eval_endを営業日にスナップ: {eval_end_raw_str} → {eval_end_snapped} (差分: {snap_diff_days}日)")
        
        portfolio = result["portfolio"]
        perf = calculate_portfolio_performance_from_dataframe(
            portfolio,
            rebalance_date,
            eval_end_snapped,
        )
        
        if "error" not in perf:
            total_return_pct = perf.get("total_return_pct", 0.0)
            topix_comp = perf.get("topix_comparison", {})
            topix_return_pct = topix_comp.get("topix_return_pct", 0.0)
            excess_return_pct = topix_comp.get("excess_return_pct", 0.0)
            
            total_return = total_return_pct / 100.0
            topix_return = topix_return_pct / 100.0
            excess_return = excess_return_pct / 100.0
            
            eval_end_used = perf.get("as_of_date", eval_end_snapped)
            annualized_ret = calculate_annualized_return_from_period(
                total_return,
                rebalance_date,
                eval_end_used,
            )
            annualized_topix_ret = calculate_annualized_return_from_period(
                topix_return,
                rebalance_date,
                eval_end_used,
            )
            annualized_excess_ret = annualized_ret - annualized_topix_ret
            
            performances.append({
                "rebalance_date": rebalance_date,
                "params_id": params_id,
                "horizon_months": horizon_months_actual or horizon_months,
                "eval_end_date": eval_end_used,
                "total_return_pct": total_return_pct,
                "topix_return_pct": topix_return_pct,
                "excess_return_pct": excess_return_pct,
                "annualized_return_pct": annualized_ret * 100.0,
                "annualized_topix_return_pct": annualized_topix_ret * 100.0,
                "annualized_excess_return_pct": annualized_excess_ret * 100.0,
            })
    
    if not performances:
        return {"error": "パフォーマンスデータがありません"}
    
    # 統計を計算
    excess_returns = [p.get("annualized_excess_return_pct", 0.0) for p in performances]
    annualized_returns = [p.get("annualized_return_pct", 0.0) for p in performances]
    
    avg_annualized_excess_return = sum(excess_returns) / len(excess_returns) if excess_returns else 0.0
    p10_excess_return = calculate_percentile(excess_returns, 10.0) if excess_returns else 0.0
    win_rate = sum(1 for r in excess_returns if r > 0) / len(excess_returns) * 100.0 if excess_returns else 0.0
    switch_count = count_switches_from_performances(performances)
    
    return {
        "avg_annualized_excess_return_pct": avg_annualized_excess_return,
        "p10_excess_return_pct": p10_excess_return,
        "win_rate_pct": win_rate,
        "switch_count": switch_count,
        "num_periods": len(performances),
        "n_periods": len(excess_returns),  # P10算出に使ったサンプル数（ChatGPT推奨）
        "performances": performances,
    }


def compare_lambda_penalties(
    params_id: str,
    start_date: str,
    end_date: str,
    n_trials: int = 200,
    n_jobs: int = -1,
    bt_workers: int = -1,
    as_of_date: Optional[str] = None,
    train_end_date: Optional[str] = None,
    lambda_values: Optional[List[float]] = None,
    version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    複数のλ値で最適化を実行し、結果を比較
    
    Args:
        params_id: パラメータID（例: "operational_24M", "12M_momentum"）
        start_date: 開始日
        end_date: 終了日
        n_trials: 試行回数
        n_jobs: trial並列数
        bt_workers: バックテスト並列数
        as_of_date: 評価の打ち切り日（Noneの場合はend_dateを使用）
        train_end_date: 学習期間の終了日（Noneの場合は"2022-12-31"）
        lambda_values: λ値のリスト（Noneの場合は[0.00, 0.05, 0.03, 0.08]）
        version: バージョン（Noneの場合は自動生成）
    
    Returns:
        比較結果
    """
    if as_of_date is None:
        as_of_date = end_date
    
    if train_end_date is None:
        train_end_date = "2022-12-31"
    
    if lambda_values is None:
        lambda_values = [0.00, 0.05, 0.03, 0.08]  # 優先順位: 0.00, 0.05, 0.03, 0.08
    
    if version is None:
        version = datetime.now().strftime("%Y%m%d")
    
    # パラメータIDからhorizon_monthsとstudy_typeを決定
    registry_entry = get_registry_entry(params_id)
    horizon_months = registry_entry.get("horizon_months")
    
    # study_typeを決定（暫定的に、horizon_monthsで判定）
    if horizon_months == 24:
        study_type = "C"  # 広範囲探索
    elif params_id == "12M_momentum":
        study_type = "A"  # BB寄り・低ROE閾値
    elif params_id == "12M_reversal":
        study_type = "B"  # Value寄り・ROE閾値やや高め
    else:
        study_type = "C"  # デフォルト
    
    # 24Mの場合はrebalance_end_dateを調整
    from dateutil.relativedelta import relativedelta
    rebalance_end_date = end_date
    if horizon_months == 24:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        end_dt_24m = end_dt - relativedelta(months=24)
        rebalance_end_date = end_dt_24m.strftime("%Y-%m-%d")
    
    print("=" * 80)
    print(f"下振れ罰係数λの比較: {params_id}")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"評価日: {as_of_date}")
    print(f"学習期間終了日: {train_end_date}")
    print(f"ホライズン: {horizon_months}M")
    print(f"試行回数: {n_trials}")
    print(f"λ値: {lambda_values}")
    print("=" * 80)
    print()
    
    results = {}
    
    for lambda_val in lambda_values:
        print(f"\n【λ={lambda_val:.2f} の最適化を開始】")
        print("-" * 80)
        
        # 最適化を実行
        study_name = f"{params_id}_lambda{lambda_val:.2f}_{version}"
        
        try:
            optimize_longterm_main(
                start_date=start_date,
                end_date=rebalance_end_date if horizon_months == 24 else end_date,
                study_type=study_type,
                n_trials=n_trials,
                study_name=study_name,
                n_jobs=n_jobs,
                bt_workers=bt_workers,
                cost_bps=0.0,
                storage=None,
                no_db_write=False,
                cache_dir="cache/features",
                train_ratio=0.8,
                random_seed=42,
                save_params=None,  # 後で処理
                params_id=f"{params_id}_lambda{lambda_val:.2f}",
                version=version,
                horizon_months=horizon_months,
                strategy_mode=None,  # 自動判定
                as_of_date=as_of_date,
                train_end_date=train_end_date,
                lambda_penalty=lambda_val,
            )
            
            # 最適化結果JSONを読み込む
            result_file = PROJECT_ROOT / f"optimization_result_{study_name}.json"
            if not result_file.exists():
                results[f"λ={lambda_val:.2f}"] = {"error": "最適化結果ファイルが見つかりません"}
                continue
            
            with open(result_file, "r", encoding="utf-8") as f:
                optimization_result = json.load(f)
            
            best_trial = optimization_result.get("best_trial", {})
            best_value = best_trial.get("value", 0.0)
            best_params = best_trial.get("params", {})
            
            # 戦略モードを判定
            strategy_mode = determine_strategy_mode(best_params)
            
            # パラメータファイルの保存
            params_file_path = save_params_file(
                optimization_result,
                f"{params_id}_lambda{lambda_val:.2f}",
                horizon_months,
                strategy_mode,
                version,
            )
            
            # バックテストを実行（test期間で評価）
            # test期間: train_end_dateより後（リバランス日ベース）
            # 注意: train_end_dateより後のリバランス日を取得する必要がある
            all_test_dates = get_monthly_rebalance_dates(start_date, end_date)
            test_dates = [d for d in all_test_dates if d > train_end_date]
            
            if not test_dates:
                results[f"λ={lambda_val:.2f}"] = {"error": "テスト期間のリバランス日が見つかりません"}
                continue
            
            # 固定パラメータモードでバックテストを実行（切替回数は常に0）
            # 注意: 固定パラメータモードでは切替が発生しないため、切替回数は0です
            # レジーム切替戦略での切替回数が必要な場合は、別途実装が必要です
            backtest_result = run_backtest_with_params_file(
                params_file_path,
                test_dates[0],  # 最初のtest期間のリバランス日
                test_dates[-1],  # 最後のtest期間のリバランス日
                as_of_date,
                require_full_horizon=True,
                rebalance_dates=test_dates,  # test期間のリバランス日を明示的に指定
            )
            
            if "error" not in backtest_result:
                # 最適化結果（train期間）のパフォーマンスも取得
                train_perf = optimization_result.get("train_performance", {})
                test_perf = optimization_result.get("test_performance", {})
                
                results[f"λ={lambda_val:.2f}"] = {
                    "lambda_penalty": lambda_val,
                    "best_objective_value": best_value,  # train期間での目的関数値
                    "train_mean_excess_return_pct": train_perf.get("mean_annual_excess_return_pct", 0.0),
                    "test_mean_excess_return_pct": test_perf.get("mean_annual_excess_return_pct", 0.0),
                    "avg_annualized_excess_return_pct": backtest_result["avg_annualized_excess_return_pct"],  # test期間での平均超過
                    "p10_excess_return_pct": backtest_result["p10_excess_return_pct"],
                    "win_rate_pct": backtest_result["win_rate_pct"],
                    "switch_count": backtest_result["switch_count"],  # 固定パラメータモードでは常に0
                    "num_periods": backtest_result["num_periods"],
                    "params_file_path": str(params_file_path),
                    "optimization_result_file": str(result_file),
                }
            else:
                results[f"λ={lambda_val:.2f}"] = {"error": backtest_result["error"]}
            
            print(f"✓ λ={lambda_val:.2f} の最適化と評価が完了しました")
            
        except Exception as e:
            import traceback
            print(f"❌ λ={lambda_val:.2f} の最適化でエラーが発生しました: {e}")
            traceback.print_exc()
            results[f"λ={lambda_val:.2f}"] = {"error": str(e)}
    
    return {
        "params_id": params_id,
        "period": {
            "start_date": start_date,
            "end_date": end_date,
            "as_of_date": as_of_date,
            "train_end_date": train_end_date,
        },
        "horizon_months": horizon_months,
        "lambda_values": lambda_values,
        "results": results,
    }


def save_comparison_results(
    comparison_data: Dict[str, Any],
    output_path: Path,
    output_format: str = "markdown",
) -> None:
    """比較結果をファイルに保存"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if output_format == "json":
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(comparison_data, f, ensure_ascii=False, indent=2)
    
    elif output_format == "markdown":
        lines = []
        lines.append(f"# 下振れ罰係数λの比較結果: {comparison_data['params_id']}")
        lines.append("")
        lines.append(f"**期間**: {comparison_data['period']['start_date']} ～ {comparison_data['period']['end_date']}")
        lines.append(f"**評価日**: {comparison_data['period']['as_of_date']}")
        lines.append(f"**学習期間終了日**: {comparison_data['period']['train_end_date']}")
        lines.append(f"**ホライズン**: {comparison_data['horizon_months']}M")
        lines.append("")
        lines.append("## 比較結果（test期間での評価）")
        lines.append("")
        lines.append("| λ値 | 平均超過(%) | P10(超過)(%) | 勝率(%) | 切替回数 | 期間数 | train超過(%) | test超過(%) |")
        lines.append("|-----|------------|-------------|---------|---------|--------|-------------|-------------|")
        
        for lambda_key, result in comparison_data["results"].items():
            if "error" in result:
                lines.append(f"| {lambda_key} | エラー | - | - | - | - | - | - |")
                continue
            
            lambda_val = result.get("lambda_penalty", 0.0)
            avg_excess = result.get("avg_annualized_excess_return_pct", 0.0)
            p10_excess = result.get("p10_excess_return_pct", 0.0)
            win_rate = result.get("win_rate_pct", 0.0)
            switch_count = result.get("switch_count", 0)
            num_periods = result.get("num_periods", 0)
            train_excess = result.get("train_mean_excess_return_pct", 0.0)
            test_excess = result.get("test_mean_excess_return_pct", 0.0)
            
            lines.append(f"| {lambda_val:.2f} | {avg_excess:.2f} | {p10_excess:.2f} | {win_rate:.1f} | {switch_count} | {num_periods} | {train_excess:.2f} | {test_excess:.2f} |")
        
        lines.append("")
        lines.append("**注意**: 切替回数は固定パラメータモードでの評価のため常に0です。レジーム切替戦略での切替回数が必要な場合は、別途実装が必要です。")
        
        lines.append("")
        lines.append("## 詳細データ")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(comparison_data, ensure_ascii=False, indent=2))
        lines.append("```")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(
        description="下振れ罰係数λの比較",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--params-id", type=str, required=True, help="パラメータID（例: operational_24M, 12M_momentum）")
    parser.add_argument("--start", type=str, required=True, help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, required=True, help="終了日（YYYY-MM-DD）")
    parser.add_argument("--n-trials", type=int, default=200, help="試行回数（デフォルト: 200）")
    parser.add_argument("--n-jobs", type=int, default=-1, help="trial並列数（-1でCPU数）")
    parser.add_argument("--bt-workers", type=int, default=-1, help="バックテスト並列数（-1で自動）")
    parser.add_argument("--as-of-date", type=str, default=None, help="評価の打ち切り日（YYYY-MM-DD、Noneの場合はend_dateを使用）")
    parser.add_argument("--train-end-date", type=str, default=None, help="学習期間の終了日（YYYY-MM-DD、Noneの場合は2022-12-31）")
    parser.add_argument("--lambda-values", type=float, nargs="+", default=None, help="λ値のリスト（デフォルト: 0.00 0.05 0.03 0.08）")
    parser.add_argument("--version", type=str, default=None, help="バージョン（Noneの場合は自動生成）")
    parser.add_argument("--output", type=str, default=None, help="出力ファイルパス")
    parser.add_argument("--output-format", type=str, choices=["json", "markdown"], default="markdown", help="出力形式")
    
    args = parser.parse_args()
    
    comparison_data = compare_lambda_penalties(
        params_id=args.params_id,
        start_date=args.start,
        end_date=args.end,
        n_trials=args.n_trials,
        n_jobs=args.n_jobs,
        bt_workers=args.bt_workers,
        as_of_date=args.as_of_date,
        train_end_date=args.train_end_date,
        lambda_values=args.lambda_values,
        version=args.version,
    )
    
    # 結果を表示
    print("\n" + "=" * 100)
    print("【比較結果（test期間での評価）】")
    print("=" * 100)
    print(f"{'λ値':<10} {'平均超過':>10} {'P10(超過)':>12} {'勝率':>8} {'切替回数':>10} {'期間数':>8} {'train超過':>12} {'test超過':>12}")
    print("-" * 100)
    
    for lambda_key, result in comparison_data["results"].items():
        if "error" in result:
            print(f"{lambda_key:<10} {'エラー':>10}")
            continue
        
        lambda_val = result.get("lambda_penalty", 0.0)
        avg_excess = result.get("avg_annualized_excess_return_pct", 0.0)
        p10_excess = result.get("p10_excess_return_pct", 0.0)
        win_rate = result.get("win_rate_pct", 0.0)
        switch_count = result.get("switch_count", 0)
        num_periods = result.get("num_periods", 0)
        train_excess = result.get("train_mean_excess_return_pct", 0.0)
        test_excess = result.get("test_mean_excess_return_pct", 0.0)
        
        print(f"{lambda_val:<10.2f} {avg_excess:>9.2f}% {p10_excess:>11.2f}% {win_rate:>7.1f}% {switch_count:>10} {num_periods:>8} {train_excess:>11.2f}% {test_excess:>11.2f}%")
    
    print("=" * 100)
    print("**注意**: 切替回数は固定パラメータモードでの評価のため常に0です。")
    print()
    
    # ファイルに保存
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = PROJECT_ROOT / "outputs" / "lambda_comparison"
        output_path = output_dir / f"lambda_comparison_{args.params_id}_{args.start}_{args.end}_{timestamp}.{args.output_format}"
    
    save_comparison_results(comparison_data, output_path, args.output_format)
    print(f"✅ 結果を {output_path} に保存しました（形式: {args.output_format}）")


if __name__ == "__main__":
    main()

