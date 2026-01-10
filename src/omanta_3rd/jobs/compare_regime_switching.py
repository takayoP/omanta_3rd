"""
切替あり vs なしの比較バックテスト（A-1）

同一期間・同一条件で次の4本を比較します：
1. 固定 24M：params_id=operational_24M を常時
2. 固定 12M_momentum：常時
3. 固定 12M_reversal：常時
4. レジーム切替：up→12M_mom / down→12M_rev / range→24M

見る指標：
- 年率リターン
- 年率超過（vs TOPIX）
- 勝率
- 最小 / P10（可能なら）

使用方法:
    python -m omanta_3rd.jobs.compare_regime_switching --start 2020-01-01 --end 2025-12-31
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
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def calculate_annualized_return(
    returns: List[float],
    periods_per_year: float = 12.0,
) -> float:
    """
    年率リターンを計算（月次リターンの累積から年率化）
    
    Args:
        returns: 各期間のリターン（小数）
        periods_per_year: 年間の期間数（デフォルト: 12.0 = 月次）
    
    Returns:
        年率リターン（小数）
    """
    if not returns:
        return 0.0
    
    # 累積リターン
    cumulative = 1.0
    for r in returns:
        cumulative *= (1.0 + r)
    
    # 年率化
    n_periods = len(returns)
    if n_periods == 0:
        return 0.0
    
    years = n_periods / periods_per_year
    if years <= 0:
        return 0.0
    
    annualized = (cumulative ** (1.0 / years)) - 1.0
    return annualized


def calculate_annualized_return_from_period(
    total_return: float,
    start_date: str,
    end_date: str,
) -> float:
    """
    期間リターンから年率リターンを計算（長期保有型用）
    
    Args:
        total_return: 総リターン（小数、例: 0.5 = 50%）
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
    
    Returns:
        年率リターン（小数）
    """
    from datetime import datetime
    
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    
    # 日数差を計算
    days_diff = (end_dt - start_dt).days
    if days_diff <= 0:
        return 0.0
    
    # 年数に変換（365.25日/年）
    years = days_diff / 365.25
    
    if years <= 0:
        return 0.0
    
    # 年率化: (1 + total_return) ^ (1 / years) - 1
    if total_return <= -1.0:
        # 完全損失の場合は-100%を返す
        return -1.0
    
    annualized = ((1.0 + total_return) ** (1.0 / years)) - 1.0
    return annualized


def calculate_percentile(returns: List[float], percentile: float) -> float:
    """
    パーセンタイルを計算
    
    Args:
        returns: リターンのリスト
        percentile: パーセンタイル（0-100）
    
    Returns:
        パーセンタイル値
    """
    if not returns:
        return 0.0
    
    return float(np.percentile(returns, percentile))


def save_results_to_file(
    output_data: Dict[str, Any],
    output_path: Path,
    output_format: Literal["json", "csv", "markdown"] = "json",
) -> None:
    """
    結果をファイルに保存
    
    Args:
        output_data: 出力データ
        output_path: 出力パス
        output_format: 出力形式（json, csv, markdown）
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if output_format == "json":
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    elif output_format == "csv":
        # CSV形式で保存（サマリーのみ）
        rows = []
        for strategy_name, result in output_data["results"].items():
            if "error" in result:
                continue
            rows.append({
                "戦略": strategy_name,
                "年率リターン(%)": result.get("annualized_return_pct", 0.0),
                "年率TOPIXリターン(%)": result.get("annualized_topix_return_pct", 0.0),
                "年率超過(%)": result.get("annualized_excess_return_pct", 0.0),
                "勝率(%)": result.get("win_rate_pct", 0.0),
                "最小リターン(総)(%)": result.get("min_return_pct", 0.0),
                "P10リターン(総)(%)": result.get("p10_return_pct", 0.0),
                "最小リターン(超過)(%)": result.get("min_excess_return_pct", 0.0),
                "P10リターン(超過)(%)": result.get("p10_excess_return_pct", 0.0),
                "期間数": result.get("num_periods", 0),
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    elif output_format == "markdown":
        # Markdown形式で保存
        lines = []
        lines.append("# 切替あり vs なしの比較バックテスト結果")
        lines.append("")
        lines.append(f"**期間**: {output_data['period']['start_date']} ～ {output_data['period']['end_date']}")
        lines.append(f"**評価日**: {output_data['period']['as_of_date']}")
        lines.append("")
        lines.append("## 比較結果")
        lines.append("")
        lines.append("| 戦略 | 年率リターン(%) | 年率超過(%) | 勝率(%) | 最小(総)(%) | P10(総)(%) | 最小(超過)(%) | P10(超過)(%) |")
        lines.append("|------|----------------|------------|---------|------------|-----------|--------------|-------------|")
        
        for strategy_name, result in output_data["results"].items():
            if "error" in result:
                lines.append(f"| {strategy_name} | エラー | - | - | - | - | - | - |")
                continue
            
            annualized_return = result.get("annualized_return_pct", 0.0)
            annualized_excess = result.get("annualized_excess_return_pct", 0.0)
            win_rate = result.get("win_rate_pct", 0.0)
            min_return = result.get("min_return_pct", 0.0)
            p10_return = result.get("p10_return_pct", 0.0)
            min_excess_return = result.get("min_excess_return_pct", 0.0)
            p10_excess_return = result.get("p10_excess_return_pct", 0.0)
            
            lines.append(
                f"| {strategy_name} | "
                f"{annualized_return:.2f} | "
                f"{annualized_excess:.2f} | "
                f"{win_rate:.1f} | "
                f"{min_return:.2f} | "
                f"{p10_return:.2f} | "
                f"{min_excess_return:.2f} | "
                f"{p10_excess_return:.2f} |"
            )
        
        lines.append("")
        lines.append("## 詳細データ")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(output_data, ensure_ascii=False, indent=2))
        lines.append("```")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))


def get_valid_rebalance_dates(
    rebalance_dates: List[str],
    horizon_months: int,
    as_of_date: str,
    require_full_horizon: bool = True,
) -> List[str]:
    """
    評価可能なrebalance_dateのリストを取得
    
    Args:
        rebalance_dates: リバランス日のリスト
        horizon_months: 投資ホライズン（月数）
        as_of_date: 評価の打ち切り日
        require_full_horizon: ホライズン未達を除外するか
    
    Returns:
        評価可能なrebalance_dateのリスト
    """
    valid_dates = []
    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    
    for rebalance_date in rebalance_dates:
        rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
        horizon_end_dt = rebalance_dt + relativedelta(months=horizon_months)
        
        if require_full_horizon:
            if horizon_end_dt > as_of_dt:
                continue  # ホライズン未達
        
        valid_dates.append(rebalance_date)
    
    return valid_dates


def compare_regime_switching(
    start_date: str,
    end_date: str,
    as_of_date: Optional[str] = None,
    output_path: str | None = None,
    output_format: Literal["json", "csv", "markdown"] = "json",
    require_full_horizon: bool = True,
    comparison_type: Literal["all", "12m_only"] = "all",
) -> Dict[str, Any]:
    """
    切替あり vs なしの比較バックテスト
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新）
        output_path: 出力パス（Noneの場合は標準出力）
    
    Returns:
        比較結果の辞書
    """
    print("=" * 80)
    print("切替あり vs なしの比較バックテスト")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    if as_of_date:
        print(f"評価日: {as_of_date}")
    else:
        print(f"評価日: 最新の価格データ")
    print(f"満了窓のみで集計: {require_full_horizon}")
    print(f"比較タイプ: {comparison_type}")
    print("=" * 80)
    print()
    
    # as_of_dateがNoneの場合はend_dateを使用（DB MAX(date)は使わない）
    if as_of_date is None:
        as_of_date = end_date
        print(f"as_of_dateが指定されていません。end_date({as_of_date})を使用します。")
        print()
    
    # リバランス日を取得
    all_rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"全リバランス日数: {len(all_rebalance_dates)}")
    print()
    
    # 比較タイプに応じて戦略を定義
    if comparison_type == "all":
        # 24Mを含める比較
        strategies = [
            {
                "name": "固定24M",
                "fixed_params_id": "operational_24M",
                "horizon_months": 24,
            },
            {
                "name": "固定12M_momentum",
                "fixed_params_id": "12M_momentum",
                "horizon_months": 12,
            },
            {
                "name": "固定12M_reversal",
                "fixed_params_id": "12M_reversal",
                "horizon_months": 12,
            },
            {
                "name": "レジーム切替",
                "fixed_params_id": None,
                "horizon_months": None,  # 可変
            },
        ]
    else:
        # 12Mだけの比較
        strategies = [
            {
                "name": "固定12M_momentum",
                "fixed_params_id": "12M_momentum",
                "horizon_months": 12,
            },
            {
                "name": "固定12M_reversal",
                "fixed_params_id": "12M_reversal",
                "horizon_months": 12,
            },
            {
                "name": "レジーム切替（12Mのみ）",
                "fixed_params_id": None,
                "horizon_months": 12,  # レジーム切替でも12Mのみ（allowed_params_idsで制限）
            },
        ]
    
    # 各戦略で評価可能なrebalance_dateを計算
    print("【評価可能なrebalance_dateを計算中...】")
    valid_dates_by_strategy = {}
    for strategy in strategies:
        strategy_name = strategy["name"]
        horizon_months = strategy["horizon_months"]
        
        if horizon_months:
            # 固定ホライズンの場合
            valid_dates = get_valid_rebalance_dates(
                all_rebalance_dates,
                horizon_months,
                as_of_date,
                require_full_horizon,
            )
        else:
            # レジーム切替の場合（可変ホライズン）
            # comparison_type="12m_only"の場合、12Mのみに制限されるため、12Mの評価可能期間を使用
            if comparison_type == "12m_only":
                valid_dates = get_valid_rebalance_dates(
                    all_rebalance_dates,
                    12,  # 12Mのみに制限
                    as_of_date,
                    require_full_horizon,
                )
            else:
                # 24Mを含む比較の場合、可変ホライズンなので一旦すべてを含める（後でフィルタ）
                valid_dates = all_rebalance_dates.copy()
        
        valid_dates_by_strategy[strategy_name] = set(valid_dates)
        print(f"  {strategy_name}: {len(valid_dates)}件")
    
    # 共通集合を計算
    if comparison_type == "all":
        # 全戦略の積集合（24Mを含む）
        common_dates = set(all_rebalance_dates)
        for strategy_name, valid_dates in valid_dates_by_strategy.items():
            common_dates = common_dates.intersection(valid_dates)
    else:
        # 12M戦略同士の積集合
        common_dates = set(all_rebalance_dates)
        for strategy_name, valid_dates in valid_dates_by_strategy.items():
            common_dates = common_dates.intersection(valid_dates)
    
    # レジーム切替戦略の場合、可変ホライズンなので実行時にフィルタする
    # ここでは固定ホライズンの戦略のみで共通集合を計算
    fixed_strategies = [s for s in strategies if s["horizon_months"] is not None]
    if fixed_strategies:
        # 固定ホライズンの戦略のみで共通集合を計算
        fixed_common_dates = set(all_rebalance_dates)
        for strategy in fixed_strategies:
            strategy_name = strategy["name"]
            if strategy_name in valid_dates_by_strategy:
                fixed_common_dates = fixed_common_dates.intersection(valid_dates_by_strategy[strategy_name])
        common_dates = sorted(list(fixed_common_dates))
    else:
        common_dates = sorted(list(common_dates))
    
    print(f"\n共通のrebalance_date集合（固定ホライズン戦略）: {len(common_dates)}件")
    if common_dates:
        print(f"  最初: {common_dates[0]}")
        print(f"  最後: {common_dates[-1]}")
    print()
    
    results = {}
    
    # 共通のrebalance_date集合を使用
    rebalance_dates = common_dates
    
    for strategy in strategies:
        strategy_name = strategy["name"]
        print(f"[{strategy_name}] ポートフォリオ作成中...")
        
        # allowed_params_idsを設定（comparison_typeに応じて）
        allowed_params_ids = None
        if comparison_type == "12m_only" and strategy["fixed_params_id"] is None:
            # 12Mだけの比較の場合、レジーム切替戦略でも12Mのみに制限
            allowed_params_ids = {"12M_momentum", "12M_reversal"}
            print(f"  [12Mのみ制限] allowed_params_ids: {allowed_params_ids}")
        
        # 各リバランス日でポートフォリオを作成
        portfolios = {}  # {rebalance_date: portfolio_df}
        portfolio_metadata = {}  # {rebalance_date: {params_id, horizon_months}}
        for rebalance_date in rebalance_dates:
            result = run_monthly_portfolio_with_regime(
                rebalance_date,
                fixed_params_id=strategy["fixed_params_id"],
                calculate_performance=False,  # 後で一括計算
                as_of_date=as_of_date,
                save_log=False,
                save_to_db=False,  # DBに保存しない（メモリ内で完結）
                allowed_params_ids=allowed_params_ids,
            )
            
            if result.get("portfolio_created") and "portfolio" in result:
                # params_idとhorizon_monthsを記録
                params_id = result.get("params_id")
                if not params_id and strategy["fixed_params_id"]:
                    # 固定戦略の場合、resultにparams_idが含まれていない可能性がある
                    params_id = strategy["fixed_params_id"]
                
                horizon_months = result.get("horizon_months")
                if not horizon_months and params_id:
                    try:
                        registry_entry = get_registry_entry(params_id)
                        horizon_months = registry_entry.get("horizon_months")
                    except Exception as e:
                        # エラーが発生した場合はスキップ
                        print(f"警告: {rebalance_date}のhorizon_months取得に失敗: {e}")
                
                # レジーム切替戦略の場合、可変ホライズンなので評価可能かチェック
                # ただし、comparison_type="12m_only"の場合、12Mのみに制限されているため、このチェックは不要
                if (strategy["fixed_params_id"] is None 
                    and horizon_months 
                    and require_full_horizon
                    and comparison_type != "12m_only"):  # 12Mだけの比較の場合はスキップ（既に12Mのみに制限されている）
                    # このrebalance_dateで使用されるhorizon_monthsで評価可能かチェック
                    rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
                    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
                    horizon_end_dt = rebalance_dt + relativedelta(months=horizon_months)
                    if horizon_end_dt > as_of_dt:
                        # ホライズン未達のためスキップ
                        continue
                
                portfolios[rebalance_date] = result["portfolio"]
                portfolio_metadata[rebalance_date] = {
                    "params_id": params_id,
                    "horizon_months": horizon_months,
                }
        
        # パフォーマンスを計算（メモリ内で完結）
        print(f"[{strategy_name}] パフォーマンス計算中...")
        performances = []
        annualized_returns = []  # 各ポートフォリオの年率リターン
        annualized_excess_returns = []  # 各ポートフォリオの年率超過リターン
        returns = []  # 総リターン（表示用）
        excess_returns = []  # 超過リターン（表示用）
        
        for rebalance_date in rebalance_dates:
            if rebalance_date not in portfolios:
                continue
            
            # 満了窓チェックと評価終点の決定（ホライズン固定評価）
            metadata = portfolio_metadata.get(rebalance_date, {})
            horizon_months = metadata.get("horizon_months")
            
            if not horizon_months:
                # horizon_monthsが取得できない場合はスキップ
                continue
            
            # eval_end = rebalance_date + horizon_months（ホライズン固定）
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_end_raw = rebalance_dt + relativedelta(months=horizon_months)
            eval_end_raw_str = eval_end_raw.strftime("%Y-%m-%d")
            
            # require_full_horizonがTrueの場合、eval_end <= as_of_dateを満たすかチェック
            as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
            if require_full_horizon:
                if eval_end_raw > as_of_dt:
                    # ホライズン未達のためスキップ
                    continue
            
            # eval_endを営業日にスナップ（価格データが存在する最新の日付を取得）
            # ただし、as_of_dateを超えないようにする（未来遮断）
            # 重要: スナップ関数の引数はeval_end_raw_strである必要がある（固定ホライズンを守るため）
            with connect_db() as conn:
                eval_end_snapped = _snap_price_date(conn, min(eval_end_raw_str, as_of_date))
                
                # スナップ差分が大きい場合（データ欠損で数週間〜数ヶ月戻るケース）は除外（ChatGPT推奨）
                eval_end_raw_dt = datetime.strptime(eval_end_raw_str, "%Y-%m-%d")
                eval_end_snapped_dt = datetime.strptime(eval_end_snapped, "%Y-%m-%d")
                snap_diff_days = (eval_end_raw_dt - eval_end_snapped_dt).days
                
                if snap_diff_days > 7:  # 1週間以上のズレは除外
                    print(f"      [compare_regime_switching] ⚠️  {rebalance_date}のeval_endスナップ差分が大きい（{snap_diff_days}日）のため除外: {eval_end_raw_str} → {eval_end_snapped}")
                    continue
                
                # require_full_horizon=Trueの場合は、固定ホライズン評価を保証するためのアサーション
                if require_full_horizon:
                    # require_full_horizon=Trueなら、eval_end_raw <= as_of_dateが保証されている
                    # また、スナップ差分が小さい（7日以内）ことも確認済み
                    assert eval_end_raw <= as_of_dt, (
                        f"require_full_horizon=True but eval_end_raw({eval_end_raw_str}) > as_of_date({as_of_date}). "
                        f"This should not happen if require_full_horizon check passed."
                    )
                    if snap_diff_days > 0:
                        print(f"      [compare_regime_switching] eval_endを営業日にスナップ: {eval_end_raw_str} → {eval_end_snapped} (差分: {snap_diff_days}日)")
            
            # 評価終点はeval_end_snapped（ホライズン固定）を使用
            # as_of_dateは未来遮断のための上限としてのみ機能
            portfolio = portfolios[rebalance_date]
            perf = calculate_portfolio_performance_from_dataframe(
                portfolio,
                rebalance_date,
                eval_end_snapped,  # ホライズン固定の評価終点
            )
            
            if "error" not in perf:
                total_return_pct = perf.get("total_return_pct", 0.0)
                topix_comp = perf.get("topix_comparison", {})
                topix_return_pct = topix_comp.get("topix_return_pct", 0.0)
                excess_return_pct = topix_comp.get("excess_return_pct", 0.0)
                
                total_return = total_return_pct / 100.0  # 小数に変換
                excess_return = excess_return_pct / 100.0  # 小数に変換
                
                returns.append(total_return)
                excess_returns.append(excess_return)
                
                # 各ポートフォリオのリターンを期間で年率化（eval_end_snappedを使用）
                # perfのas_of_dateにはeval_end_snappedが入っている
                eval_end_used = perf.get("as_of_date", eval_end_snapped)
                annualized_ret = calculate_annualized_return_from_period(
                    total_return,
                    rebalance_date,
                    eval_end_used,
                )
                annualized_returns.append(annualized_ret)
                
                # TOPIXの年率リターンも計算（eval_end_snappedを使用）
                topix_return = topix_return_pct / 100.0
                annualized_topix_ret = calculate_annualized_return_from_period(
                    topix_return,
                    rebalance_date,
                    eval_end_used,
                )
                annualized_excess_ret = annualized_ret - annualized_topix_ret
                annualized_excess_returns.append(annualized_excess_ret)
                
                # params_idとhorizon_monthsを追加
                metadata = portfolio_metadata.get(rebalance_date, {})
                performances.append({
                    "rebalance_date": rebalance_date,
                    "params_id": metadata.get("params_id"),
                    "horizon_months": metadata.get("horizon_months"),
                    "eval_end_date": eval_end_used,  # 使用した評価終点を記録
                    "total_return_pct": total_return_pct,
                    "topix_return_pct": topix_return_pct,
                    "excess_return_pct": excess_return_pct,
                    "annualized_return_pct": annualized_ret * 100.0,
                    "annualized_excess_return_pct": annualized_excess_ret * 100.0,
                })
        
        # 指標を計算
        if annualized_returns:
            # 年率リターンの平均
            annualized_return = sum(annualized_returns) / len(annualized_returns) * 100.0
            
            # TOPIXの年率リターンも平均
            # 注意: 各パフォーマンスは既にeval_endで年率化されているので、
            # ここでは単純に平均を取る（再計算は不要）
            topix_returns = [p.get("topix_return_pct", 0.0) / 100.0 for p in performances]
            # 各パフォーマンスのeval_endで年率化されたTOPIXリターンを計算
            annualized_topix_returns = []
            for p in performances:
                topix_return = p.get("topix_return_pct", 0.0) / 100.0
                rebalance_date_perf = p.get("rebalance_date")
                eval_end_used_perf = p.get("eval_end_date", as_of_date)  # eval_end_dateが記録されていれば使用
                annualized_topix_ret = calculate_annualized_return_from_period(
                    topix_return,
                    rebalance_date_perf,
                    eval_end_used_perf,
                )
                annualized_topix_returns.append(annualized_topix_ret)
            annualized_topix_return = sum(annualized_topix_returns) / len(annualized_topix_returns) * 100.0 if annualized_topix_returns else 0.0
            annualized_excess_return = annualized_return - annualized_topix_return
            
            # 勝率（超過リターンが正の期間の割合）
            win_rate = sum(1 for r in excess_returns if r > 0) / len(excess_returns) * 100.0 if excess_returns else 0.0
            
            # 最小 / P10（年率化されたリターンで計算）
            min_return = min(annualized_returns) * 100.0 if annualized_returns else 0.0
            p10_return = calculate_percentile(annualized_returns, 10.0) * 100.0 if annualized_returns else 0.0
            
            # 最小 / P10（年率化された超過リターンで計算）
            min_excess_return = min(annualized_excess_returns) * 100.0 if annualized_excess_returns else 0.0
            p10_excess_return = calculate_percentile(annualized_excess_returns, 10.0) * 100.0 if annualized_excess_returns else 0.0
            
            # レジーム別・選択別の分解統計
            regime_stats = {}
            params_id_stats = {}
            
            for perf in performances:
                # レジーム切替戦略の場合のみ、params_idが記録されている
                params_id = perf.get("params_id")
                if params_id:
                    if params_id not in params_id_stats:
                        params_id_stats[params_id] = {
                            "count": 0,
                            "annualized_returns": [],
                            "annualized_excess_returns": [],
                        }
                    params_id_stats[params_id]["count"] += 1
                    params_id_stats[params_id]["annualized_returns"].append(perf.get("annualized_return_pct", 0.0) / 100.0)
                    params_id_stats[params_id]["annualized_excess_returns"].append(perf.get("annualized_excess_return_pct", 0.0) / 100.0)
            
            # params_id別の平均を計算
            params_id_summary = {}
            for params_id, stats in params_id_stats.items():
                if stats["annualized_returns"]:
                    params_id_summary[params_id] = {
                        "count": stats["count"],
                        "avg_annualized_return_pct": sum(stats["annualized_returns"]) / len(stats["annualized_returns"]) * 100.0,
                        "avg_annualized_excess_return_pct": sum(stats["annualized_excess_returns"]) / len(stats["annualized_excess_returns"]) * 100.0,
                    }
            
            results[strategy_name] = {
                "annualized_return_pct": annualized_return,
                "annualized_topix_return_pct": annualized_topix_return,
                "annualized_excess_return_pct": annualized_excess_return,
                "win_rate_pct": win_rate,
                "min_return_pct": min_return,
                "p10_return_pct": p10_return,
                "min_excess_return_pct": min_excess_return,
                "p10_excess_return_pct": p10_excess_return,
                "num_periods": len(returns),
                "num_periods_included": len(annualized_returns),  # 実際に集計に含まれた期間数
                "n_periods": len(annualized_excess_returns),  # P10算出に使ったサンプル数（ChatGPT推奨）
                "performances": performances,
                "params_id_summary": params_id_summary,  # レジーム切替戦略の場合のみ
            }
        else:
            results[strategy_name] = {
                "error": "パフォーマンスデータが取得できませんでした",
            }
        
        print(f"[{strategy_name}] ✅ 完了")
        print()
    
    # 結果を表示
    print("=" * 80)
    print("【比較結果】")
    print("=" * 80)
    
    # 表形式で表示
    print(f"{'戦略':<20} {'年率リターン':>12} {'年率超過':>12} {'勝率':>8} {'最小(総)':>10} {'P10(総)':>10} {'最小(超過)':>12} {'P10(超過)':>12}")
    print("-" * 100)
    
    for strategy_name, result in results.items():
        if "error" in result:
            print(f"{strategy_name:<20} {'エラー':>12}")
            continue
        
        annualized_return = result.get("annualized_return_pct", 0.0)
        annualized_excess = result.get("annualized_excess_return_pct", 0.0)
        win_rate = result.get("win_rate_pct", 0.0)
        min_return = result.get("min_return_pct", 0.0)
        p10_return = result.get("p10_return_pct", 0.0)
        min_excess_return = result.get("min_excess_return_pct", 0.0)
        p10_excess_return = result.get("p10_excess_return_pct", 0.0)
        
        print(
            f"{strategy_name:<20} "
            f"{annualized_return:>11.2f}% "
            f"{annualized_excess:>11.2f}% "
            f"{win_rate:>7.1f}% "
            f"{min_return:>9.2f}% "
            f"{p10_return:>9.2f}% "
            f"{min_excess_return:>11.2f}% "
            f"{p10_excess_return:>11.2f}%"
        )
    
    print("=" * 80)
    print()
    
    # 結果を出力
    output_data = {
        "period": {
            "start_date": start_date,
            "end_date": end_date,
            "as_of_date": as_of_date,
            "require_full_horizon": require_full_horizon,
        },
        "results": results,
    }
    
    # 出力パスが指定されていない場合は、デフォルトのファイル名を生成
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = PROJECT_ROOT / "outputs" / "regime_comparison"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # ファイル拡張子を形式に応じて設定
        ext_map = {
            "json": ".json",
            "csv": ".csv",
            "markdown": ".md",
        }
        ext = ext_map.get(output_format, ".json")
        
        # 比較タイプに応じてファイル名を変更
        type_suffix = {
            "all": "all_strategies",
            "12m_only": "12m_only",
        }.get(comparison_type, "all_strategies")
        
        output_path = str(output_dir / f"regime_comparison_{type_suffix}_{start_date}_{end_date}_{timestamp}{ext}")
    
    output_file = Path(output_path)
    save_results_to_file(output_data, output_file, output_format)
    print(f"✅ 結果を {output_path} に保存しました（形式: {output_format}）")
    
    # JSON形式も同時に保存（詳細データ用）
    if output_format != "json":
        json_path = output_file.with_suffix('.json')
        save_results_to_file(output_data, json_path, "json")
        print(f"✅ 詳細データ（JSON）を {json_path} に保存しました")
    
    print("=" * 80)
    
    return output_data


def run_both_comparisons(
    start_date: str,
    end_date: str,
    as_of_date: Optional[str] = None,
    require_full_horizon: bool = True,
) -> Dict[str, Any]:
    """
    2つの比較を実行（24Mを含める比較と12Mだけの比較）
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新）
        require_full_horizon: 満了窓のみで集計するか（デフォルト: True）
    
    Returns:
        両方の比較結果を含む辞書
    """
    print("=" * 80)
    print("Step 2: A-1比較の再集計（共通のrebalance_date集合で比較）")
    print("=" * 80)
    print()
    
    # 1. 24Mを含める比較
    print("【比較1: 24Mを含める比較（全戦略の積集合）】")
    print("=" * 80)
    result_all = compare_regime_switching(
        start_date=start_date,
        end_date=end_date,
        as_of_date=as_of_date,
        output_path=None,  # 自動生成
        output_format="markdown",
        require_full_horizon=require_full_horizon,
        comparison_type="all",
    )
    print()
    
    # 2. 12Mだけの比較
    print("【比較2: 12Mだけの比較（12M戦略同士の積集合）】")
    print("=" * 80)
    result_12m = compare_regime_switching(
        start_date=start_date,
        end_date=end_date,
        as_of_date=as_of_date,
        output_path=None,  # 自動生成
        output_format="markdown",
        require_full_horizon=require_full_horizon,
        comparison_type="12m_only",
    )
    print()
    
    return {
        "comparison_all": result_all,
        "comparison_12m_only": result_12m,
    }


def main(
    start_date: str,
    end_date: str,
    as_of_date: Optional[str] = None,
    output_path: str | None = None,
    output_format: Literal["json", "csv", "markdown"] = "json",
    require_full_horizon: bool = True,
    comparison_type: Literal["all", "12m_only", "both"] = "both",
):
    """
    メイン処理
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新）
        output_path: 出力パス（Noneの場合は自動生成）
        output_format: 出力形式（json, csv, markdown）
        require_full_horizon: 満了窓のみで集計するか（デフォルト: True）
        comparison_type: 比較タイプ（"all", "12m_only", "both"）
    """
    if comparison_type == "both":
        result = run_both_comparisons(start_date, end_date, as_of_date, require_full_horizon)
        return 0
    else:
        result = compare_regime_switching(
            start_date, end_date, as_of_date, output_path, output_format, require_full_horizon, comparison_type
        )
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="切替あり vs なしの比較バックテスト",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 比較バックテストを実行
  python -m omanta_3rd.jobs.compare_regime_switching --start 2020-01-01 --end 2025-12-31
  
  # 結果をファイルに保存
  python -m omanta_3rd.jobs.compare_regime_switching --start 2020-01-01 --end 2025-12-31 --output outputs/regime_comparison.json
  
  # 特定の評価日で計算
  python -m omanta_3rd.jobs.compare_regime_switching --start 2020-01-01 --end 2025-12-31 --as-of-date 2025-12-31
        """
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
        "--as-of-date",
        type=str,
        dest="as_of_date",
        default=None,
        help="評価日（YYYY-MM-DD、Noneの場合は最新の価格データを使用）",
    )
    parser.add_argument(
        "--output",
        type=str,
        dest="output_path",
        default=None,
        help="出力パス（指定しない場合は自動生成: outputs/regime_comparison/regime_comparison_YYYYMMDD_HHMMSS.{ext}）",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "csv", "markdown"],
        default="json",
        dest="output_format",
        help="出力形式（デフォルト: json）",
    )
    parser.add_argument(
        "--require-full-horizon",
        action="store_true",
        default=True,
        dest="require_full_horizon",
        help="満了窓のみで集計する（デフォルト: True、ホライズン未達の期間を除外）",
    )
    parser.add_argument(
        "--no-require-full-horizon",
        action="store_false",
        dest="require_full_horizon",
        help="すべての期間を含めて集計する（ホライズン未達の期間も含む）",
    )
    parser.add_argument(
        "--comparison-type",
        type=str,
        choices=["all", "12m_only", "both"],
        default="both",
        dest="comparison_type",
        help="比較タイプ: 'all'=24Mを含める比較, '12m_only'=12Mだけの比較, 'both'=両方実行（デフォルト: both）",
    )
    
    args = parser.parse_args()
    
    sys.exit(main(
        start_date=args.start,
        end_date=args.end,
        as_of_date=args.as_of_date,
        output_path=args.output_path,
        output_format=args.output_format,
        require_full_horizon=args.require_full_horizon,
        comparison_type=args.comparison_type,
    ))

