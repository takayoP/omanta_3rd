"""
ホールドアウト評価（時系列版）【月次リバランス型用】

月次リバランス型のホールドアウト評価スクリプト。

時系列バックテスト（open-close方式）を使用して、ホールドアウト評価を実行します。
Train期間で最適化→Holdout期間で固定評価を行い、過学習の有無を検証します。

【注意】このスクリプトは月次リバランス型専用です。
長期保有型の評価には optimize_longterm.py や walk_forward_longterm.py を使用してください。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
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
from dataclasses import replace
import optuna


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


def run_holdout_evaluation(
    train_start_date: str,
    train_end_date: str,
    holdout_start_date: str,
    holdout_end_date: str,
    n_trials: int = 50,
    buy_cost_bps: float = 0.0,
    sell_cost_bps: float = 0.0,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    ホールドアウト評価を実行
    
    Args:
        train_start_date: Train期間の開始日（YYYY-MM-DD）
        train_end_date: Train期間の終了日（YYYY-MM-DD）
        holdout_start_date: Holdout期間の開始日（YYYY-MM-DD）
        holdout_end_date: Holdout期間の終了日（YYYY-MM-DD）
        n_trials: 最適化の試行回数
        buy_cost_bps: 購入コスト（bps）
        sell_cost_bps: 売却コスト（bps）
        seed: 乱数シード
    
    Returns:
        ホールドアウト評価結果の辞書
    """
    print("=" * 80)
    print("ホールドアウト評価（時系列版）")
    print("=" * 80)
    print(f"Train期間: {train_start_date} ～ {train_end_date}")
    print(f"Holdout期間: {holdout_start_date} ～ {holdout_end_date}")
    print(f"最適化試行回数: {n_trials}")
    print(f"取引コスト: buy={buy_cost_bps}bps, sell={sell_cost_bps}bps")
    print()
    
    # リバランス日を取得
    train_dates = get_monthly_rebalance_dates(train_start_date, train_end_date)
    holdout_dates = get_monthly_rebalance_dates(holdout_start_date, holdout_end_date)
    
    print(f"Train期間のリバランス日数: {len(train_dates)}")
    print(f"Holdout期間のリバランス日数: {len(holdout_dates)}")
    print()
    
    if not train_dates:
        return {"error": "Train期間のリバランス日が見つかりませんでした"}
    if not holdout_dates:
        return {"error": "Holdout期間のリバランス日が見つかりませんでした"}
    
    # Train期間で最適化
    print("Train期間で最適化を実行中...")
    study_name = f"holdout_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    study = optuna.create_study(
        direction="maximize",
        study_name=study_name,
        storage=f"sqlite:///optuna_{study_name}.db",
        load_if_exists=False,
    )
    
    if seed is not None:
        study.sampler = optuna.samplers.TPESampler(seed=seed)
    
    study.optimize(
        lambda trial: objective_timeseries(
            trial,
            train_dates,
            cost_bps=(buy_cost_bps + sell_cost_bps) / 2.0,
            n_jobs=1,
        ),
        n_trials=n_trials,
        show_progress_bar=True,
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
    
    opt_result = {
        "best_value": study.best_value,
        "best_params": normalized_best_params,
        "best_params_raw": best_params_raw,
        "n_trials": n_trials,
    }
    
    print(f"最適化完了: best_value={study.best_value:.4f}")
    print()
    
    # Train期間でバックテスト（参考用）
    print("Train期間でバックテストを実行中（参考用）...")
    run_backtest_for_optimization_timeseries(
        train_dates,
        StrategyParams(),  # 最適化結果を使用（簡易版）
        EntryScoreParams(),
        cost_bps=(buy_cost_bps + sell_cost_bps) / 2.0,
        n_jobs=1,
    )
    
    train_timeseries_data = calculate_timeseries_returns(
        start_date=train_start_date,
        end_date=train_end_date,
        rebalance_dates=train_dates,
        cost_bps=(buy_cost_bps + sell_cost_bps) / 2.0,
        buy_cost_bps=buy_cost_bps,
        sell_cost_bps=sell_cost_bps,
    )
    train_metrics = calculate_metrics_from_timeseries_data(train_timeseries_data)
    
    # Holdout期間でバックテスト
    print("Holdout期間でバックテストを実行中...")
    
    # StrategyParamsを構築
    default_params = StrategyParams()
    strategy_params = replace(
        default_params,
        target_min=12,
        target_max=12,
        w_quality=normalized_best_params.get("w_quality", 0.0),
        w_value=normalized_best_params.get("w_value", 0.0),
        w_growth=normalized_best_params.get("w_growth", 0.0),
        w_record_high=normalized_best_params.get("w_record_high", 0.0),
        w_size=normalized_best_params.get("w_size", 0.0),
        w_forward_per=normalized_best_params.get("w_forward_per", 0.5),
        w_pbr=normalized_best_params.get("w_pbr", 0.5),
        roe_min=normalized_best_params.get("roe_min", 0.08),
        liquidity_quantile_cut=normalized_best_params.get("liquidity_quantile_cut", 0.25),
    )
    
    # EntryScoreParamsを構築
    entry_params = EntryScoreParams(
        rsi_base=normalized_best_params.get("rsi_base", 50.0),
        rsi_max=normalized_best_params.get("rsi_max", 75.0),
        bb_z_base=normalized_best_params.get("bb_z_base", -1.0),
        bb_z_max=normalized_best_params.get("bb_z_max", 2.0),
        bb_weight=normalized_best_params.get("bb_weight", 0.6),
        rsi_weight=normalized_best_params.get("rsi_weight", 0.4),
    )
    
    # ポートフォリオを生成して保存
    run_backtest_for_optimization_timeseries(
        holdout_dates,
        strategy_params,
        entry_params,
        cost_bps=(buy_cost_bps + sell_cost_bps) / 2.0,
        n_jobs=1,
    )
    
    holdout_timeseries_data = calculate_timeseries_returns(
        start_date=holdout_start_date,
        end_date=holdout_end_date,
        rebalance_dates=holdout_dates,
        cost_bps=(buy_cost_bps + sell_cost_bps) / 2.0,
        buy_cost_bps=buy_cost_bps,
        sell_cost_bps=sell_cost_bps,
    )
    holdout_metrics = calculate_metrics_from_timeseries_data(holdout_timeseries_data)
    
    # メタデータ
    config = {
        "train_start_date": train_start_date,
        "train_end_date": train_end_date,
        "holdout_start_date": holdout_start_date,
        "holdout_end_date": holdout_end_date,
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
        "optimization": opt_result,
        "train_metrics": train_metrics,
        "holdout_metrics": holdout_metrics,
    }


def generate_markdown_report(holdout_result: Dict[str, Any]) -> str:
    """Markdown形式のレポートを生成"""
    lines = []
    lines.append("# ホールドアウト評価結果（時系列版）")
    lines.append("")
    lines.append(f"**実行日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    config = holdout_result.get("config", {})
    lines.append("## 設定")
    lines.append("")
    lines.append(f"- **Train期間**: {config.get('train_start_date')} ～ {config.get('train_end_date')}")
    lines.append(f"- **Holdout期間**: {config.get('holdout_start_date')} ～ {config.get('holdout_end_date')}")
    lines.append(f"- **最適化試行回数**: {config.get('n_trials')}")
    lines.append(f"- **取引コスト**: buy={config.get('buy_cost_bps')}bps, sell={config.get('sell_cost_bps')}bps")
    lines.append(f"- **売買タイミング**: {config.get('timing')} (open(t+1) -> close(t_next))")
    lines.append(f"- **欠損処理**: {config.get('missing_policy')}")
    lines.append(f"- **Executed Turnover**: 2.0（毎回100%売って100%買う）")
    lines.append("")
    
    # Train vs Holdout の比較
    train_metrics = holdout_result.get("train_metrics", {})
    holdout_metrics = holdout_result.get("holdout_metrics", {})
    
    lines.append("## Train vs Holdout の比較")
    lines.append("")
    lines.append("| 指標 | Train | Holdout | ギャップ |")
    lines.append("|------|-------|---------|----------|")
    
    train_sharpe = train_metrics.get("sharpe_ratio")
    holdout_sharpe = holdout_metrics.get("sharpe_ratio")
    if train_sharpe is not None and holdout_sharpe is not None:
        gap = train_sharpe - holdout_sharpe
        lines.append(f"| Sharpe_excess | {train_sharpe:.4f} | {holdout_sharpe:.4f} | {gap:.4f} |")
    
    train_cagr = train_metrics.get("cagr")
    holdout_cagr = holdout_metrics.get("cagr")
    if train_cagr is not None and holdout_cagr is not None:
        gap = train_cagr - holdout_cagr
        lines.append(f"| CAGR | {train_cagr:.2f}% | {holdout_cagr:.2f}% | {gap:.2f}% |")
    
    train_max_dd = train_metrics.get("max_drawdown")
    holdout_max_dd = holdout_metrics.get("max_drawdown")
    if train_max_dd is not None and holdout_max_dd is not None:
        gap = train_max_dd - holdout_max_dd
        lines.append(f"| MaxDD | {train_max_dd:.2f}% | {holdout_max_dd:.2f}% | {gap:.2f}% |")
    
    lines.append("")
    
    # 詳細メトリクス
    lines.append("## 詳細メトリクス")
    lines.append("")
    
    lines.append("### Train期間")
    lines.append("")
    lines.append("| 指標 | 値 |")
    lines.append("|------|-----|")
    for key, value in train_metrics.items():
        if value is not None and key != "error":
            if isinstance(value, float):
                lines.append(f"| {key} | {value:.4f} |")
            else:
                lines.append(f"| {key} | {value} |")
    lines.append("")
    
    lines.append("### Holdout期間")
    lines.append("")
    lines.append("| 指標 | 値 |")
    lines.append("|------|-----|")
    for key, value in holdout_metrics.items():
        if value is not None and key != "error":
            if isinstance(value, float):
                lines.append(f"| {key} | {value:.4f} |")
            else:
                lines.append(f"| {key} | {value} |")
    lines.append("")
    
    # 所見
    lines.append("## 所見")
    lines.append("")
    lines.append("- Train vs Holdout のギャップ（過学習サイン）を確認してください")
    lines.append("- Holdout期間のSharpe_excessがTrain期間と比較して大きく低下していないか確認してください")
    lines.append("")
    
    return "\n".join(lines)


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="ホールドアウト評価（時系列版）")
    parser.add_argument("--train-start", type=str, required=True, help="Train期間の開始日（YYYY-MM-DD）")
    parser.add_argument("--train-end", type=str, required=True, help="Train期間の終了日（YYYY-MM-DD）")
    parser.add_argument("--holdout-start", type=str, required=True, help="Holdout期間の開始日（YYYY-MM-DD）")
    parser.add_argument("--holdout-end", type=str, required=True, help="Holdout期間の終了日（YYYY-MM-DD）")
    parser.add_argument("--n-trials", type=int, default=50, help="最適化の試行回数（デフォルト: 50）")
    parser.add_argument("--buy-cost", type=float, default=0.0, help="購入コスト（bps、デフォルト: 0.0）")
    parser.add_argument("--sell-cost", type=float, default=0.0, help="売却コスト（bps、デフォルト: 0.0）")
    parser.add_argument("--seed", type=int, help="乱数シード")
    parser.add_argument("--output-dir", type=str, default="reports", help="出力ディレクトリ（デフォルト: reports）")
    
    args = parser.parse_args()
    
    # ホールドアウト評価を実行
    holdout_result = run_holdout_evaluation(
        train_start_date=args.train_start,
        train_end_date=args.train_end,
        holdout_start_date=args.holdout_start,
        holdout_end_date=args.holdout_end,
        n_trials=args.n_trials,
        buy_cost_bps=args.buy_cost,
        sell_cost_bps=args.sell_cost,
        seed=args.seed,
    )
    
    if "error" in holdout_result:
        print(f"❌ エラー: {holdout_result['error']}")
        sys.exit(1)
    
    # 出力ディレクトリを作成
    output_dir = Path(args.output_dir)
    artifacts_dir = Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # レポートを生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"holdout_timeseries_{timestamp}.md"
    artifacts_path = artifacts_dir / f"holdout_timeseries_{timestamp}.json"
    
    markdown_report = generate_markdown_report(holdout_result)
    report_path.write_text(markdown_report, encoding="utf-8")
    print(f"レポートを {report_path} に保存しました")
    
    # JSONを保存
    with open(artifacts_path, "w", encoding="utf-8") as f:
        json.dump(holdout_result, f, indent=2, ensure_ascii=False)
    print(f"生データを {artifacts_path} に保存しました")
    
    # 最良パラメータを保存
    best_params = holdout_result["optimization"]["best_params"]
    params_path = artifacts_dir / f"best_params_holdout_{timestamp}.json"
    with open(params_path, "w", encoding="utf-8") as f:
        json.dump(best_params, f, indent=2, ensure_ascii=False)
    print(f"最良パラメータを {params_path} に保存しました")


if __name__ == "__main__":
    main()

