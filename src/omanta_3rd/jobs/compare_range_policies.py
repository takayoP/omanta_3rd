"""
Step3: rangeレジームポリシーの比較（A-1の拡張）

rangeレジームでの3つのポリシーを比較します：
1. 案A: range → 12M_momentum（レンジは短めで回す）
2. 案B: range → 前回params_id維持（ヒステリシス）（レンジでフリップしない）
3. 案C: range → 24Mのまま（現状）

評価は「24M込み（共通48期間）」で揃えます。

追加出力：
- レジーム別成績（up/range/down別の平均超過、P10、勝率）
- レジーム×params_idの条件付き成績（例：rangeの時に24Mを使った場合の超過）
- 切替回数

使用方法:
    python -m omanta_3rd.jobs.compare_range_policies --start 2020-01-01 --end 2025-12-31
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Literal
import pandas as pd
import numpy as np

from ..infra.db import connect_db
from ..jobs.batch_longterm_run import get_monthly_rebalance_dates
from ..jobs.batch_longterm_run_with_regime import run_monthly_portfolio_with_regime
from ..backtest.performance_from_dataframe import calculate_portfolio_performance_from_dataframe
from ..config.settings import PROJECT_ROOT
from ..config.params_registry import get_registry_entry
from ..jobs.longterm_run import _snap_price_date
from ..market.regime import get_market_regime
from dateutil.relativedelta import relativedelta


def calculate_annualized_return_from_period(
    total_return: float,
    start_date: str,
    end_date: str,
) -> float:
    """
    期間リターンから年率リターンを計算（長期保有型用）
    """
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
    if not returns:
        return 0.0
    return float(np.percentile(returns, percentile))


def run_regime_switching_with_hysteresis(
    rebalance_dates: List[str],
    as_of_date: str,
    range_policy: Literal["12M_momentum", "hysteresis", "24M"],
    require_full_horizon: bool = True,
    save_to_db: bool = False,
) -> Dict[str, Any]:
    """
    ヒステリシス対応のレジーム切替を実行
    
    Args:
        rebalance_dates: リバランス日のリスト
        as_of_date: 評価日
        range_policy: rangeレジームのポリシー
            - "12M_momentum": range → 12M_momentum
            - "hysteresis": range → 前回params_id維持
            - "24M": range → operational_24M（現状）
        require_full_horizon: 満了窓のみ集計するか
        save_to_db: データベースに保存するか
    
    Returns:
        結果辞書（portfolios, portfolio_metadata, performances）
    """
    portfolios = {}  # {rebalance_date: portfolio_df}
    portfolio_metadata = {}  # {rebalance_date: {params_id, horizon_months, regime}}
    last_params_id = None  # 前回のparams_id（ヒステリシス用）
    
    # レジームポリシーの基本マッピング（range以外）
    base_policy = {
        "up": "12M_momentum",
        "down": "12M_momentum",  # 12M_reversalを除外したため
    }
    
    for rebalance_date in rebalance_dates:
        with connect_db() as conn:
            # レジーム判定
            regime_info = get_market_regime(conn, rebalance_date)
            regime = regime_info["regime"]
            
            # params_idを決定
            if regime == "range":
                if range_policy == "12M_momentum":
                    params_id = "12M_momentum"
                elif range_policy == "hysteresis":
                    # ヒステリシス: 前回のparams_idを維持（初回は12M_momentum）
                    params_id = last_params_id if last_params_id else "12M_momentum"
                elif range_policy == "24M":
                    params_id = "operational_24M"
                else:
                    raise ValueError(f"Unknown range_policy: {range_policy}")
            else:
                params_id = base_policy.get(regime, "12M_momentum")
            
            # ポートフォリオを作成（固定モードで実行）
            result = run_monthly_portfolio_with_regime(
                rebalance_date,
                fixed_params_id=params_id,  # 固定モードで実行
                calculate_performance=False,
                as_of_date=as_of_date,
                save_log=False,
                save_to_db=save_to_db,
                allowed_params_ids=None,
            )
            
            if result.get("portfolio_created") and "portfolio" in result:
                # 満了窓チェック
                horizon_months = result.get("horizon_months")
                if horizon_months and require_full_horizon:
                    rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
                    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
                    horizon_end_dt = rebalance_dt + relativedelta(months=horizon_months)
                    if horizon_end_dt > as_of_dt:
                        # ホライズン未達のためスキップ（ヒステリシスは更新しない）
                        continue
                
                portfolios[rebalance_date] = result["portfolio"]
                # 固定モードではregimeが"fixed"になるため、手動でレジーム情報を保存
                portfolio_metadata[rebalance_date] = {
                    "params_id": params_id,
                    "horizon_months": horizon_months,
                    "regime": regime,  # 手動で保存したレジーム情報
                }
                
                # ヒステリシス用に前回params_idを更新
                last_params_id = params_id
    
    # パフォーマンスを計算
    performances = []
    for rebalance_date in portfolios.keys():
        metadata = portfolio_metadata[rebalance_date]
        horizon_months = metadata.get("horizon_months")
        
        if not horizon_months:
            continue
        
        # eval_end = rebalance_date + horizon_months（ホライズン固定）
        rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
        eval_end_raw = rebalance_dt + relativedelta(months=horizon_months)
        eval_end_raw_str = eval_end_raw.strftime("%Y-%m-%d")
        
        # require_full_horizonがTrueの場合、eval_end <= as_of_dateを満たすかチェック
        if require_full_horizon:
            as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
            if eval_end_raw > as_of_dt:
                continue
        
        # eval_endを営業日にスナップ
        with connect_db() as conn:
            eval_end_snapped = _snap_price_date(conn, min(eval_end_raw_str, as_of_date))
        
        portfolio = portfolios[rebalance_date]
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
                "params_id": metadata.get("params_id"),
                "horizon_months": metadata.get("horizon_months"),
                "regime": metadata.get("regime"),
                "eval_end_date": eval_end_used,
                "total_return_pct": total_return_pct,
                "topix_return_pct": topix_return_pct,
                "excess_return_pct": excess_return_pct,
                "annualized_return_pct": annualized_ret * 100.0,
                "annualized_topix_return_pct": annualized_topix_ret * 100.0,
                "annualized_excess_return_pct": annualized_excess_ret * 100.0,
            })
    
    return {
        "portfolios": portfolios,
        "portfolio_metadata": portfolio_metadata,
        "performances": performances,
    }


def calculate_regime_breakdown(performances: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    レジーム別の成績を計算
    
    Args:
        performances: パフォーマンスのリスト
    
    Returns:
        レジーム別の成績
    """
    regime_performances = {
        "up": [],
        "down": [],
        "range": [],
    }
    
    for perf in performances:
        regime = perf.get("regime")
        if regime in regime_performances:
            regime_performances[regime].append(perf)
    
    regime_stats = {}
    for regime, perfs in regime_performances.items():
        if not perfs:
            regime_stats[regime] = {
                "count": 0,
                "avg_annualized_excess_return_pct": 0.0,
                "p10_excess_return_pct": 0.0,
                "win_rate_pct": 0.0,
            }
            continue
        
        excess_returns = [p.get("annualized_excess_return_pct", 0.0) for p in perfs]
        win_count = sum(1 for r in excess_returns if r > 0)
        
        regime_stats[regime] = {
            "count": len(perfs),
            "avg_annualized_excess_return_pct": sum(excess_returns) / len(excess_returns) if excess_returns else 0.0,
            "p10_excess_return_pct": calculate_percentile(excess_returns, 10.0) if excess_returns else 0.0,
            "win_rate_pct": (win_count / len(excess_returns) * 100.0) if excess_returns else 0.0,
        }
    
    return regime_stats


def calculate_regime_params_breakdown(performances: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    レジーム×params_idの条件付き成績を計算
    
    Args:
        performances: パフォーマンスのリスト
    
    Returns:
        レジーム×params_id別の成績
        {regime: {params_id: stats}}
    """
    breakdown = {}
    
    for perf in performances:
        regime = perf.get("regime")
        params_id = perf.get("params_id")
        
        if regime not in breakdown:
            breakdown[regime] = {}
        if params_id not in breakdown[regime]:
            breakdown[regime][params_id] = []
        
        breakdown[regime][params_id].append(perf)
    
    # 統計を計算
    result = {}
    for regime, params_dict in breakdown.items():
        result[regime] = {}
        for params_id, perfs in params_dict.items():
            excess_returns = [p.get("annualized_excess_return_pct", 0.0) for p in perfs]
            win_count = sum(1 for r in excess_returns if r > 0)
            
            result[regime][params_id] = {
                "count": len(perfs),
                "avg_annualized_excess_return_pct": sum(excess_returns) / len(excess_returns) if excess_returns else 0.0,
                "p10_excess_return_pct": calculate_percentile(excess_returns, 10.0) if excess_returns else 0.0,
                "win_rate_pct": (win_count / len(excess_returns) * 100.0) if excess_returns else 0.0,
            }
    
    return result


def count_switches(portfolio_metadata: Dict[str, Dict[str, Any]]) -> int:
    """
    切替回数をカウント
    
    Args:
        portfolio_metadata: {rebalance_date: {params_id, ...}}
    
    Returns:
        切替回数
    """
    if len(portfolio_metadata) < 2:
        return 0
    
    sorted_dates = sorted(portfolio_metadata.keys())
    switch_count = 0
    prev_params_id = None
    
    for rebalance_date in sorted_dates:
        current_params_id = portfolio_metadata[rebalance_date].get("params_id")
        if prev_params_id is not None and current_params_id != prev_params_id:
            switch_count += 1
        prev_params_id = current_params_id
    
    return switch_count


def compare_range_policies(
    start_date: str,
    end_date: str,
    as_of_date: Optional[str] = None,
    require_full_horizon: bool = True,
) -> Dict[str, Any]:
    """
    rangeレジームポリシーの3案を比較
    
    Args:
        start_date: 開始日
        end_date: 終了日
        as_of_date: 評価日（Noneの場合はend_dateを使用）
        require_full_horizon: 満了窓のみ集計するか
    
    Returns:
        比較結果
    """
    if as_of_date is None:
        as_of_date = end_date
    
    # リバランス日を取得（24Mが完走できる範囲に制限）
    all_dates = get_monthly_rebalance_dates(start_date, end_date)
    
    # 24Mが完走できる範囲（eval_end <= as_of_date）を計算
    valid_dates_24m = []
    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    for rebalance_date in all_dates:
        rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
        eval_end_dt = rebalance_dt + relativedelta(months=24)
        if eval_end_dt <= as_of_dt:
            valid_dates_24m.append(rebalance_date)
    
    print(f"有効なリバランス日数（24M完走可能）: {len(valid_dates_24m)}")
    if valid_dates_24m:
        print(f"  最初: {valid_dates_24m[0]}")
        print(f"  最後: {valid_dates_24m[-1]}")
    print()
    
    policies = [
        {"name": "案A: range → 12M_momentum", "policy": "12M_momentum"},
        {"name": "案B: range → ヒステリシス", "policy": "hysteresis"},
        {"name": "案C: range → 24Mのまま", "policy": "24M"},
    ]
    
    results = {}
    
    for policy_info in policies:
        policy_name = policy_info["name"]
        range_policy = policy_info["policy"]
        
        print(f"[{policy_name}] 実行中...")
        
        # レジーム切替を実行
        result_data = run_regime_switching_with_hysteresis(
            valid_dates_24m,
            as_of_date,
            range_policy,
            require_full_horizon=require_full_horizon,
            save_to_db=False,
        )
        
        performances = result_data["performances"]
        portfolio_metadata = result_data["portfolio_metadata"]
        
        if not performances:
            results[policy_name] = {"error": "パフォーマンスデータがありません"}
            continue
        
        # 全体統計を計算
        excess_returns = [p.get("annualized_excess_return_pct", 0.0) for p in performances]
        annualized_returns = [p.get("annualized_return_pct", 0.0) for p in performances]
        topix_returns = [p.get("annualized_topix_return_pct", 0.0) for p in performances]
        
        avg_annualized_return = sum(annualized_returns) / len(annualized_returns) if annualized_returns else 0.0
        avg_annualized_topix_return = sum(topix_returns) / len(topix_returns) if topix_returns else 0.0
        avg_annualized_excess_return = sum(excess_returns) / len(excess_returns) if excess_returns else 0.0
        win_rate = sum(1 for r in excess_returns if r > 0) / len(excess_returns) * 100.0 if excess_returns else 0.0
        
        min_return = min(annualized_returns) if annualized_returns else 0.0
        p10_return = calculate_percentile(annualized_returns, 10.0) if annualized_returns else 0.0
        min_excess_return = min(excess_returns) if excess_returns else 0.0
        p10_excess_return = calculate_percentile(excess_returns, 10.0) if excess_returns else 0.0
        
        # レジーム別統計
        regime_breakdown = calculate_regime_breakdown(performances)
        
        # レジーム×params_id別統計
        regime_params_breakdown = calculate_regime_params_breakdown(performances)
        
        # 切替回数
        switch_count = count_switches(portfolio_metadata)
        
        # params_id別サマリー
        params_id_summary = {}
        for perf in performances:
            params_id = perf.get("params_id")
            if params_id not in params_id_summary:
                params_id_summary[params_id] = {
                    "count": 0,
                    "excess_returns": [],
                }
            params_id_summary[params_id]["count"] += 1
            params_id_summary[params_id]["excess_returns"].append(perf.get("annualized_excess_return_pct", 0.0))
        
        # 平均を計算
        for params_id, data in params_id_summary.items():
            excess_rs = data["excess_returns"]
            params_id_summary[params_id] = {
                "count": data["count"],
                "avg_annualized_excess_return_pct": sum(excess_rs) / len(excess_rs) if excess_rs else 0.0,
            }
        
        results[policy_name] = {
            "annualized_return_pct": avg_annualized_return,
            "annualized_topix_return_pct": avg_annualized_topix_return,
            "annualized_excess_return_pct": avg_annualized_excess_return,
            "win_rate_pct": win_rate,
            "min_return_pct": min_return,
            "p10_return_pct": p10_return,
            "min_excess_return_pct": min_excess_return,
            "p10_excess_return_pct": p10_excess_return,
            "num_periods": len(performances),
            "switch_count": switch_count,
            "regime_breakdown": regime_breakdown,
            "regime_params_breakdown": regime_params_breakdown,
            "params_id_summary": params_id_summary,
            "performances": performances,
        }
        
        print(f"  ✓ 完了: {len(performances)}期間, 切替回数: {switch_count}")
        print(f"  年率超過: {avg_annualized_excess_return:.2f}%, 勝率: {win_rate:.1f}%")
        print()
    
    return {
        "period": {
            "start_date": start_date,
            "end_date": end_date,
            "as_of_date": as_of_date,
            "require_full_horizon": require_full_horizon,
        },
        "results": results,
    }


def save_results(
    output_data: Dict[str, Any],
    output_path: Path,
    output_format: Literal["json", "markdown"] = "json",
) -> None:
    """結果をファイルに保存"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if output_format == "json":
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    elif output_format == "markdown":
        lines = []
        lines.append("# Step3: rangeレジームポリシー比較結果")
        lines.append("")
        lines.append(f"**期間**: {output_data['period']['start_date']} ～ {output_data['period']['end_date']}")
        lines.append(f"**評価日**: {output_data['period']['as_of_date']}")
        lines.append("")
        lines.append("## 比較結果サマリー")
        lines.append("")
        lines.append("| ポリシー | 年率超過(%) | 勝率(%) | P10(超過)(%) | 最小(超過)(%) | 切替回数 |")
        lines.append("|---------|------------|---------|-------------|--------------|---------|")
        
        for policy_name, result in output_data["results"].items():
            if "error" in result:
                lines.append(f"| {policy_name} | エラー | - | - | - | - |")
                continue
            
            excess = result.get("annualized_excess_return_pct", 0.0)
            win_rate = result.get("win_rate_pct", 0.0)
            p10_excess = result.get("p10_excess_return_pct", 0.0)
            min_excess = result.get("min_excess_return_pct", 0.0)
            switch_count = result.get("switch_count", 0)
            
            lines.append(f"| {policy_name} | {excess:.2f} | {win_rate:.1f} | {p10_excess:.2f} | {min_excess:.2f} | {switch_count} |")
        
        lines.append("")
        lines.append("## レジーム別成績")
        lines.append("")
        
        for policy_name, result in output_data["results"].items():
            if "error" in result:
                continue
            
            lines.append(f"### {policy_name}")
            lines.append("")
            regime_breakdown = result.get("regime_breakdown", {})
            
            lines.append("| レジーム | 件数 | 平均超過(%) | P10(超過)(%) | 勝率(%) |")
            lines.append("|---------|------|------------|-------------|---------|")
            
            for regime in ["up", "down", "range"]:
                stats = regime_breakdown.get(regime, {})
                count = stats.get("count", 0)
                avg_excess = stats.get("avg_annualized_excess_return_pct", 0.0)
                p10_excess = stats.get("p10_excess_return_pct", 0.0)
                win_rate = stats.get("win_rate_pct", 0.0)
                
                lines.append(f"| {regime} | {count} | {avg_excess:.2f} | {p10_excess:.2f} | {win_rate:.1f} |")
            
            lines.append("")
        
        lines.append("## レジーム×params_id別成績（rangeレジーム）")
        lines.append("")
        
        for policy_name, result in output_data["results"].items():
            if "error" in result:
                continue
            
            lines.append(f"### {policy_name}")
            lines.append("")
            regime_params_breakdown = result.get("regime_params_breakdown", {})
            range_breakdown = regime_params_breakdown.get("range", {})
            
            if range_breakdown:
                lines.append("| params_id | 件数 | 平均超過(%) | P10(超過)(%) | 勝率(%) |")
                lines.append("|-----------|------|------------|-------------|---------|")
                
                for params_id, stats in range_breakdown.items():
                    count = stats.get("count", 0)
                    avg_excess = stats.get("avg_annualized_excess_return_pct", 0.0)
                    p10_excess = stats.get("p10_excess_return_pct", 0.0)
                    win_rate = stats.get("win_rate_pct", 0.0)
                    
                    lines.append(f"| {params_id} | {count} | {avg_excess:.2f} | {p10_excess:.2f} | {win_rate:.1f} |")
            else:
                lines.append("rangeレジームのデータがありません")
            
            lines.append("")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description="Step3: rangeレジームポリシー比較")
    parser.add_argument("--start", type=str, required=True, help="開始日 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, required=True, help="終了日 (YYYY-MM-DD)")
    parser.add_argument("--as-of-date", type=str, default=None, help="評価日 (YYYY-MM-DD, デフォルト: end)")
    parser.add_argument("--output", type=str, default=None, help="出力ファイルパス")
    parser.add_argument("--output-format", type=str, choices=["json", "markdown"], default="json", help="出力形式")
    parser.add_argument("--require-full-horizon", action="store_true", default=True, help="満了窓のみ集計（デフォルト: True）")
    
    args = parser.parse_args()
    
    output_data = compare_range_policies(
        args.start,
        args.end,
        as_of_date=args.as_of_date,
        require_full_horizon=args.require_full_horizon,
    )
    
    # 結果を表示
    print("\n" + "=" * 80)
    print("【比較結果】")
    print("=" * 80)
    print(f"{'ポリシー':<40} {'年率超過':>10} {'勝率':>8} {'P10(超過)':>12} {'切替回数':>10}")
    print("-" * 80)
    
    for policy_name, result in output_data["results"].items():
        if "error" in result:
            print(f"{policy_name:<40} {'エラー':>10}")
            continue
        
        excess = result.get("annualized_excess_return_pct", 0.0)
        win_rate = result.get("win_rate_pct", 0.0)
        p10_excess = result.get("p10_excess_return_pct", 0.0)
        switch_count = result.get("switch_count", 0)
        
        print(f"{policy_name:<40} {excess:>9.2f}% {win_rate:>7.1f}% {p10_excess:>11.2f}% {switch_count:>10}")
    
    print("=" * 80)
    print()
    
    # ファイルに保存
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = PROJECT_ROOT / "outputs" / "range_policy_comparison"
        output_path = output_dir / f"range_policy_comparison_{args.start}_{args.end}_{timestamp}.{args.output_format}"
    
    save_results(output_data, output_path, args.output_format)
    print(f"✅ 結果を {output_path} に保存しました（形式: {args.output_format}）")


if __name__ == "__main__":
    main()

