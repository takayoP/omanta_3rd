"""
Walk-Forward Analysis（時系列版）【月次リバランス型用】

月次リバランス型のWalk-Forward Analysisスクリプト。

時系列バックテスト（open-close方式）を使用して、Walk-Forward Analysisを実行します。
過学習の有無を検証するため、train期間で最適化→test期間で固定評価を繰り返します。

【注意】このスクリプトは月次リバランス型専用です。
長期保有型のWFAには walk_forward_longterm.py を使用してください。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import optuna
import subprocess

from ..infra.db import connect_db
from ..jobs.batch_longterm_run import get_monthly_rebalance_dates
from ..jobs.optimize_timeseries import (
    run_backtest_for_optimization_timeseries,
    objective_timeseries,
)
from ..jobs.longterm_run import StrategyParams
from ..jobs.optimize import EntryScoreParams
from ..backtest.timeseries import calculate_timeseries_returns
from ..backtest.eval_common import calculate_metrics_from_timeseries_data
from dataclasses import replace, fields


def get_git_commit_hash() -> Optional[str]:
    """Gitコミットハッシュを取得"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def split_dates_into_folds(
    all_dates: List[str],
    n_folds: int,
    train_min_years: float = 2.0,
) -> List[Dict[str, Any]]:
    """
    リバランス日をfoldに分割
    
    Args:
        all_dates: 全リバランス日のリスト
        n_folds: fold数
        train_min_years: 最小train期間（年）
    
    Returns:
        foldごとの辞書リスト: [{"train_dates": [...], "test_dates": [...]}, ...]
    """
    if len(all_dates) < 2:
        return []
    
    folds = []
    total_months = len(all_dates)
    
    # 最小train期間（月数）
    train_min_months = int(train_min_years * 12)
    
    # foldごとに分割
    for fold_idx in range(n_folds):
        # train期間の終了位置（foldが進むにつれて拡大）
        train_end_idx = train_min_months + fold_idx * (total_months - train_min_months) // n_folds
        
        # test期間の開始位置（train期間の直後）
        test_start_idx = train_end_idx + 1
        
        # test期間の終了位置（次のfoldの開始、または最後）
        if fold_idx < n_folds - 1:
            test_end_idx = train_min_months + (fold_idx + 1) * (total_months - train_min_months) // n_folds
        else:
            test_end_idx = total_months - 1
        
        if test_start_idx > test_end_idx:
            continue  # test期間が存在しない場合はスキップ
        
        train_dates = all_dates[:train_end_idx + 1]
        test_dates = all_dates[test_start_idx:test_end_idx + 1]
        
        if len(train_dates) < train_min_months or len(test_dates) == 0:
            continue
        
        folds.append({
            "fold": fold_idx + 1,
            "train_dates": train_dates,
            "test_dates": test_dates,
            "train_start": train_dates[0],
            "train_end": train_dates[-1],
            "test_start": test_dates[0],
            "test_end": test_dates[-1],
        })
    
    return folds


def run_optimization_for_fold(
    train_dates: List[str],
    n_trials: int,
    buy_cost_bps: float,
    sell_cost_bps: float,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    foldのtrain期間で最適化を実行
    
    Args:
        train_dates: train期間のリバランス日リスト
        n_trials: 試行回数
        buy_cost_bps: 購入コスト（bps）
        sell_cost_bps: 売却コスト（bps）
        seed: 乱数シード
    
    Returns:
        最適化結果の辞書（best_params含む）
    """
    print(f"  Train期間で最適化を実行中... (n_trials={n_trials})")
    
    # Optunaスタディを作成
    study_name = f"wfa_fold_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    study = optuna.create_study(
        direction="maximize",
        study_name=study_name,
        storage=f"sqlite:///optuna_{study_name}.db",
        load_if_exists=False,
    )
    
    if seed is not None:
        study.sampler = optuna.samplers.TPESampler(seed=seed)
    
    # 最適化実行
    study.optimize(
        lambda trial: objective_timeseries(
            trial,
            train_dates,
            cost_bps=(buy_cost_bps + sell_cost_bps) / 2.0,  # 平均値を使用（後で分離対応）
            n_jobs=1,  # WFAでは逐次実行
        ),
        n_trials=n_trials,
        show_progress_bar=False,
    )
    
    # 最良パラメータを取得
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
    
    normalized_best_params = best_params_raw.copy()
    normalized_best_params["w_quality"] = w_quality_norm
    normalized_best_params["w_value"] = w_value_norm
    normalized_best_params["w_growth"] = w_growth_norm
    normalized_best_params["w_record_high"] = w_record_high_norm
    normalized_best_params["w_size"] = w_size_norm
    
    return {
        "best_value": study.best_value,
        "best_params": normalized_best_params,
        "best_params_raw": best_params_raw,
        "n_trials": n_trials,
    }


def run_backtest_with_fixed_params(
    test_dates: List[str],
    best_params: Dict[str, Any],
    buy_cost_bps: float,
    sell_cost_bps: float,
) -> Dict[str, Any]:
    """
    固定パラメータでtest期間のバックテストを実行
    
    Args:
        test_dates: test期間のリバランス日リスト
        best_params: 最適化で得られたパラメータ
        buy_cost_bps: 購入コスト（bps）
        sell_cost_bps: 売却コスト（bps）
    
    Returns:
        メトリクスの辞書
    """
    print(f"  Test期間でバックテストを実行中...")
    
    # StrategyParamsを構築
    default_params = StrategyParams()
    strategy_params = replace(
        default_params,
        target_min=12,
        target_max=12,
        w_quality=best_params.get("w_quality", 0.0),
        w_value=best_params.get("w_value", 0.0),
        w_growth=best_params.get("w_growth", 0.0),
        w_record_high=best_params.get("w_record_high", 0.0),
        w_size=best_params.get("w_size", 0.0),
        w_forward_per=best_params.get("w_forward_per", 0.5),
        w_pbr=best_params.get("w_pbr", 0.5),
        roe_min=best_params.get("roe_min", 0.08),
        liquidity_quantile_cut=best_params.get("liquidity_quantile_cut", 0.25),
    )
    
    # EntryScoreParamsを構築
    entry_params = EntryScoreParams(
        rsi_base=best_params.get("rsi_base", 50.0),
        rsi_max=best_params.get("rsi_max", 75.0),
        bb_z_base=best_params.get("bb_z_base", -1.0),
        bb_z_max=best_params.get("bb_z_max", 2.0),
        bb_weight=best_params.get("bb_weight", 0.6),
        rsi_weight=best_params.get("rsi_weight", 0.4),
    )
    
    # ポートフォリオを生成して保存
    run_backtest_for_optimization_timeseries(
        test_dates,
        strategy_params,
        entry_params,
        cost_bps=(buy_cost_bps + sell_cost_bps) / 2.0,  # 平均値を使用
        n_jobs=1,
    )
    
    # 時系列P/Lを計算
    start_date = test_dates[0]
    end_date = test_dates[-1]
    
    timeseries_data = calculate_timeseries_returns(
        start_date=start_date,
        end_date=end_date,
        rebalance_dates=test_dates,
        cost_bps=(buy_cost_bps + sell_cost_bps) / 2.0,
        buy_cost_bps=buy_cost_bps,
        sell_cost_bps=sell_cost_bps,
    )
    
    # メトリクスを計算
    metrics = calculate_metrics_from_timeseries_data(timeseries_data)
    
    return metrics


def run_walk_forward_analysis(
    start_date: str,
    end_date: str,
    n_folds: int = 3,
    train_min_years: float = 2.0,
    n_trials: int = 50,
    buy_cost_bps: float = 0.0,
    sell_cost_bps: float = 0.0,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Walk-Forward Analysisを実行
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        n_folds: fold数
        train_min_years: 最小train期間（年）
        n_trials: 最適化の試行回数
        buy_cost_bps: 購入コスト（bps）
        sell_cost_bps: 売却コスト（bps）
        seed: 乱数シード
    
    Returns:
        WFA結果の辞書
    """
    print("=" * 80)
    print("Walk-Forward Analysis（時系列版）")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"Fold数: {n_folds}")
    print(f"最小Train期間: {train_min_years}年")
    print(f"最適化試行回数: {n_trials}")
    print(f"取引コスト: buy={buy_cost_bps}bps, sell={sell_cost_bps}bps")
    print()
    
    # リバランス日を取得
    all_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"全リバランス日数: {len(all_dates)}")
    if not all_dates:
        return {"error": "リバランス日が見つかりませんでした"}
    
    # foldに分割
    folds = split_dates_into_folds(all_dates, n_folds, train_min_years)
    print(f"生成されたfold数: {len(folds)}")
    print()
    
    if not folds:
        return {"error": "foldが生成されませんでした"}
    
    # foldごとに実行
    fold_results = []
    
    for fold_info in folds:
        fold_num = fold_info["fold"]
        train_dates = fold_info["train_dates"]
        test_dates = fold_info["test_dates"]
        
        print(f"Fold {fold_num}/{len(folds)}")
        print(f"  Train: {fold_info['train_start']} ～ {fold_info['train_end']} ({len(train_dates)}期間)")
        print(f"  Test:  {fold_info['test_start']} ～ {fold_info['test_end']} ({len(test_dates)}期間)")
        
        # 最適化
        opt_result = run_optimization_for_fold(
            train_dates,
            n_trials,
            buy_cost_bps,
            sell_cost_bps,
            seed,
        )
        
        # バックテスト
        test_metrics = run_backtest_with_fixed_params(
            test_dates,
            opt_result["best_params"],
            buy_cost_bps,
            sell_cost_bps,
        )
        
        fold_results.append({
            "fold": fold_num,
            "train_period": {
                "start": fold_info["train_start"],
                "end": fold_info["train_end"],
                "num_periods": len(train_dates),
            },
            "test_period": {
                "start": fold_info["test_start"],
                "end": fold_info["test_end"],
                "num_periods": len(test_dates),
            },
            "optimization": opt_result,
            "test_metrics": test_metrics,
        })
        
        print(f"  Test Sharpe_excess: {test_metrics.get('sharpe_ratio', 'N/A'):.4f}" if test_metrics.get('sharpe_ratio') else "  Test Sharpe_excess: N/A")
        print()
    
    # 集計
    test_sharpes = [
        r["test_metrics"].get("sharpe_ratio")
        for r in fold_results
        if r["test_metrics"].get("sharpe_ratio") is not None
    ]
    test_cagrs = [
        r["test_metrics"].get("cagr")
        for r in fold_results
        if r["test_metrics"].get("cagr") is not None
    ]
    test_max_dds = [
        r["test_metrics"].get("max_drawdown")
        for r in fold_results
        if r["test_metrics"].get("max_drawdown") is not None
    ]
    
    summary = {
        "test_sharpe_mean": float(np.mean(test_sharpes)) if test_sharpes else None,
        "test_sharpe_std": float(np.std(test_sharpes, ddof=1)) if len(test_sharpes) > 1 else None,
        "test_sharpe_min": float(np.min(test_sharpes)) if test_sharpes else None,
        "test_sharpe_max": float(np.max(test_sharpes)) if test_sharpes else None,
        "test_cagr_mean": float(np.mean(test_cagrs)) if test_cagrs else None,
        "test_max_dd_mean": float(np.mean(test_max_dds)) if test_max_dds else None,
    }
    
    # メタデータ
    config = {
        "start_date": start_date,
        "end_date": end_date,
        "n_folds": n_folds,
        "train_min_years": train_min_years,
        "n_trials": n_trials,
        "buy_cost_bps": buy_cost_bps,
        "sell_cost_bps": sell_cost_bps,
        "seed": seed,
        "timing": "open-close",
        "missing_policy": "drop_and_renormalize",
        "commit_hash": get_git_commit_hash(),
    }
    
    return {
        "config": config,
        "folds": fold_results,
        "summary": summary,
    }


def generate_markdown_report(wfa_result: Dict[str, Any]) -> str:
    """Markdown形式のレポートを生成"""
    lines = []
    lines.append("# Walk-Forward Analysis 結果（時系列版）")
    lines.append("")
    lines.append(f"**実行日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    config = wfa_result.get("config", {})
    lines.append("## 設定")
    lines.append("")
    lines.append(f"- **期間**: {config.get('start_date')} ～ {config.get('end_date')}")
    lines.append(f"- **Fold数**: {config.get('n_folds')}")
    lines.append(f"- **最小Train期間**: {config.get('train_min_years')}年")
    lines.append(f"- **最適化試行回数**: {config.get('n_trials')}")
    lines.append(f"- **取引コスト**: buy={config.get('buy_cost_bps')}bps, sell={config.get('sell_cost_bps')}bps")
    lines.append(f"- **売買タイミング**: {config.get('timing')} (open(t+1) -> close(t_next))")
    lines.append(f"- **欠損処理**: {config.get('missing_policy')}")
    lines.append(f"- **Executed Turnover**: 2.0（毎回100%売って100%買う）")
    lines.append("")
    
    # 集計
    summary = wfa_result.get("summary", {})
    lines.append("## 集計結果（Test期間）")
    lines.append("")
    lines.append("| 指標 | 平均 | 標準偏差 | 最小 | 最大 |")
    lines.append("|------|------|----------|------|------|")
    
    sharpe_mean = summary.get("test_sharpe_mean")
    sharpe_std = summary.get("test_sharpe_std")
    sharpe_min = summary.get("test_sharpe_min")
    sharpe_max = summary.get("test_sharpe_max")
    
    if sharpe_mean is not None:
        lines.append(
            f"| Sharpe_excess | {sharpe_mean:.4f} | "
            f"{sharpe_std:.4f if sharpe_std else 'N/A'} | "
            f"{sharpe_min:.4f} | {sharpe_max:.4f} |"
        )
    
    cagr_mean = summary.get("test_cagr_mean")
    if cagr_mean is not None:
        lines.append(f"| CAGR | {cagr_mean:.2f}% | - | - | - |")
    
    max_dd_mean = summary.get("test_max_dd_mean")
    if max_dd_mean is not None:
        lines.append(f"| MaxDD | {max_dd_mean:.2f}% | - | - | - |")
    
    lines.append("")
    
    # foldごとの詳細
    lines.append("## Foldごとの詳細")
    lines.append("")
    
    for fold_result in wfa_result.get("folds", []):
        fold_num = fold_result["fold"]
        train_period = fold_result["train_period"]
        test_period = fold_result["test_period"]
        test_metrics = fold_result["test_metrics"]
        
        lines.append(f"### Fold {fold_num}")
        lines.append("")
        lines.append(f"- **Train期間**: {train_period['start']} ～ {train_period['end']} ({train_period['num_periods']}期間)")
        lines.append(f"- **Test期間**: {test_period['start']} ～ {test_period['end']} ({test_period['num_periods']}期間)")
        lines.append("")
        lines.append("**Test期間のメトリクス**:")
        lines.append("")
        lines.append("| 指標 | 値 |")
        lines.append("|------|-----|")
        
        if test_metrics.get("cagr") is not None:
            lines.append(f"| CAGR | {test_metrics['cagr']:.2f}% |")
        if test_metrics.get("max_drawdown") is not None:
            lines.append(f"| MaxDD | {test_metrics['max_drawdown']:.2f}% |")
        if test_metrics.get("sharpe_ratio") is not None:
            lines.append(f"| Sharpe_excess | {test_metrics['sharpe_ratio']:.4f} |")
        if test_metrics.get("sortino_ratio") is not None:
            lines.append(f"| Sortino_excess | {test_metrics['sortino_ratio']:.4f} |")
        if test_metrics.get("total_return") is not None:
            lines.append(f"| Total Return | {test_metrics['total_return']:.2f}% |")
        if test_metrics.get("num_missing_stocks") is not None:
            lines.append(f"| 欠損銘柄数 | {test_metrics['num_missing_stocks']}件 |")
        
        lines.append("")
    
    # 所見
    lines.append("## 所見")
    lines.append("")
    lines.append("- Train vs Test のギャップ（過学習サイン）を確認してください")
    lines.append("- Test期間のSharpe_excessが安定しているか確認してください")
    lines.append("")
    
    return "\n".join(lines)


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="Walk-Forward Analysis（時系列版）")
    parser.add_argument("--start", type=str, required=True, help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, required=True, help="終了日（YYYY-MM-DD）")
    parser.add_argument("--folds", type=int, default=3, help="Fold数（デフォルト: 3）")
    parser.add_argument("--train-min-years", type=float, default=2.0, help="最小Train期間（年、デフォルト: 2.0）")
    parser.add_argument("--n-trials", type=int, default=50, help="最適化の試行回数（デフォルト: 50）")
    parser.add_argument("--buy-cost", type=float, default=0.0, help="購入コスト（bps、デフォルト: 0.0）")
    parser.add_argument("--sell-cost", type=float, default=0.0, help="売却コスト（bps、デフォルト: 0.0）")
    parser.add_argument("--seed", type=int, help="乱数シード")
    parser.add_argument("--output-dir", type=str, default="reports", help="出力ディレクトリ（デフォルト: reports）")
    
    args = parser.parse_args()
    
    # WFAを実行
    wfa_result = run_walk_forward_analysis(
        start_date=args.start,
        end_date=args.end,
        n_folds=args.folds,
        train_min_years=args.train_min_years,
        n_trials=args.n_trials,
        buy_cost_bps=args.buy_cost,
        sell_cost_bps=args.sell_cost,
        seed=args.seed,
    )
    
    if "error" in wfa_result:
        print(f"❌ エラー: {wfa_result['error']}")
        sys.exit(1)
    
    # 出力ディレクトリを作成
    output_dir = Path(args.output_dir)
    artifacts_dir = Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # レポートを生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"wfa_timeseries_{timestamp}.md"
    artifacts_path = artifacts_dir / f"wfa_timeseries_{timestamp}.json"
    
    markdown_report = generate_markdown_report(wfa_result)
    report_path.write_text(markdown_report, encoding="utf-8")
    print(f"レポートを {report_path} に保存しました")
    
    # JSONを保存
    with open(artifacts_path, "w", encoding="utf-8") as f:
        json.dump(wfa_result, f, indent=2, ensure_ascii=False)
    print(f"生データを {artifacts_path} に保存しました")
    
    # foldごとのbest_paramsを保存
    for fold_result in wfa_result.get("folds", []):
        fold_num = fold_result["fold"]
        best_params = fold_result["optimization"]["best_params"]
        params_path = artifacts_dir / f"best_params_fold{fold_num}_{timestamp}.json"
        with open(params_path, "w", encoding="utf-8") as f:
            json.dump(best_params, f, indent=2, ensure_ascii=False)
        print(f"Fold {fold_num}の最良パラメータを {params_path} に保存しました")


if __name__ == "__main__":
    main()

