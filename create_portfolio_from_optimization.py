"""
最適化結果のパラメータを使ってポートフォリオを作成し、パフォーマンスを計算

最適化結果ファイル（optimization_result_optimization_20251229_212329.json）から
パラメータを読み込み、同じ期間でポートフォリオを作成します。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import replace, fields
import pandas as pd

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import (
    build_features,
    StrategyParams,
    save_portfolio,
)
from omanta_3rd.jobs.optimize import (
    EntryScoreParams,
    _select_portfolio_with_params,
    _calculate_entry_score_with_params,
)
from omanta_3rd.jobs.batch_monthly_run import get_monthly_rebalance_dates
from omanta_3rd.backtest.performance import (
    calculate_portfolio_performance,
    save_performance_to_db,
)


def load_optimization_result(result_file: str) -> Dict[str, Any]:
    """最適化結果ファイルを読み込む"""
    with open(result_file, "r", encoding="utf-8") as f:
        return json.load(f)


def create_portfolio_with_optimized_params(
    start_date: str,
    end_date: str,
    optimization_result: Dict[str, Any],
) -> None:
    """
    最適化結果のパラメータを使ってポートフォリオを作成し、パフォーマンスを計算
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        optimization_result: 最適化結果の辞書
    """
    print("=" * 80)
    print("最適化結果パラメータでのポートフォリオ作成")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print("=" * 80)
    print()
    
    # 最適化結果からパラメータを取得
    best_params = optimization_result["best_params"]
    
    # StrategyParamsを作成
    # 重みの正規化（合計が1になるように）
    w_quality = best_params["w_quality"]
    w_value = best_params["w_value"]
    w_growth = best_params["w_growth"]
    w_record_high = best_params["w_record_high"]
    w_size = best_params["w_size"]
    
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
    
    # EntryScoreParamsを作成
    entry_params = EntryScoreParams(
        rsi_base=best_params["rsi_base"],
        rsi_max=best_params["rsi_max"],
        bb_z_base=best_params["bb_z_base"],
        bb_z_max=best_params["bb_z_max"],
        bb_weight=best_params["bb_weight"],
        rsi_weight=1.0 - best_params["bb_weight"],
    )
    
    print("【使用パラメータ】")
    print(f"  w_quality: {w_quality:.4f}")
    print(f"  w_value: {w_value:.4f}")
    print(f"  w_growth: {w_growth:.4f}")
    print(f"  w_record_high: {w_record_high:.4f}")
    print(f"  w_size: {w_size:.4f}")
    print(f"  w_forward_per: {best_params['w_forward_per']:.4f}")
    print(f"  roe_min: {best_params['roe_min']:.4f}")
    print(f"  liquidity_quantile_cut: {best_params['liquidity_quantile_cut']:.4f}")
    print(f"  rsi_base: {best_params['rsi_base']:.2f}")
    print(f"  rsi_max: {best_params['rsi_max']:.2f}")
    print(f"  bb_z_base: {best_params['bb_z_base']:.2f}")
    print(f"  bb_z_max: {best_params['bb_z_max']:.2f}")
    print(f"  bb_weight: {best_params['bb_weight']:.4f}")
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
    
    # ポートフォリオを作成
    print("=" * 80)
    print("ポートフォリオ作成中...")
    print("=" * 80)
    
    success_count = 0
    error_count = 0
    
    for i, rebalance_date in enumerate(rebalance_dates, 1):
        print(f"[{i}/{len(rebalance_dates)}] {rebalance_date} のポートフォリオを作成中...")
        
        try:
            with connect_db() as conn:
                # 特徴量を構築
                feat = build_features(conn, rebalance_date)
                
                if feat is None or feat.empty:
                    print(f"  ⚠️  特徴量が空です（スキップ）")
                    error_count += 1
                    continue
                
                # entry_scoreを計算（最適化パラメータを使用）
                feat = _calculate_entry_score_with_params(feat, entry_params)
                
                # ポートフォリオを選定（最適化パラメータを使用）
                portfolio = _select_portfolio_with_params(
                    feat, strategy_params, entry_params
                )
                
                if portfolio is None or portfolio.empty:
                    print(f"  ⚠️  ポートフォリオが空です（スキップ）")
                    error_count += 1
                    continue
                
                # 保存
                save_portfolio(conn, portfolio)
                
                print(f"  ✅ ポートフォリオ作成完了: {len(portfolio)}銘柄")
                success_count += 1
                
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            error_count += 1
    
    print()
    print("=" * 80)
    print("ポートフォリオ作成結果")
    print("=" * 80)
    print(f"成功: {success_count}/{len(rebalance_dates)}")
    print(f"エラー: {error_count}/{len(rebalance_dates)}")
    print()
    
    # パフォーマンスを計算
    print("=" * 80)
    print("パフォーマンス計算中...")
    print("=" * 80)
    
    performance_results: List[Dict[str, Any]] = []
    
    for i, rebalance_date in enumerate(rebalance_dates, 1):
        print(f"[{i}/{len(rebalance_dates)}] {rebalance_date} のパフォーマンスを計算中...")
        
        try:
            perf = calculate_portfolio_performance(rebalance_date, as_of_date=end_date)
            
            if "error" not in perf:
                performance_results.append(perf)
                save_performance_to_db(perf)
                
                total_return = perf.get("total_return_pct")
                topix_return = perf.get("topix_comparison", {}).get("topix_return_pct")
                excess_return = perf.get("topix_comparison", {}).get("excess_return_pct")
                
                print(f"  ✅ パフォーマンス計算完了", end="")
                if total_return is not None:
                    print(f" (リターン: {total_return:.2f}%)", end="")
                if topix_return is not None:
                    print(f" | TOPIX: {topix_return:.2f}%", end="")
                if excess_return is not None:
                    print(f" | 超過: {excess_return:.2f}%", end="")
                print()
            else:
                print(f"  ❌ パフォーマンス計算エラー: {perf.get('error')}")
                
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            import traceback
            traceback.print_exc()
    
    # サマリー表示
    if performance_results:
        print()
        print("=" * 80)
        print("【バックテスト結果サマリー】")
        print("=" * 80)
        
        total_returns = [p.get("total_return_pct") for p in performance_results if p.get("total_return_pct") is not None]
        topix_returns = [p.get("topix_comparison", {}).get("topix_return_pct") for p in performance_results if p.get("topix_comparison", {}).get("topix_return_pct") is not None]
        excess_returns = [p.get("topix_comparison", {}).get("excess_return_pct") for p in performance_results if p.get("topix_comparison", {}).get("excess_return_pct") is not None]
        win_rates = [p.get("topix_comparison", {}).get("win_rate") for p in performance_results if p.get("topix_comparison", {}).get("win_rate") is not None]
        sharpe_ratios = [p.get("sharpe_ratio") for p in performance_results if p.get("sharpe_ratio") is not None]
        
        if total_returns:
            print(f"平均総リターン: {sum(total_returns) / len(total_returns):.2f}%")
        if topix_returns:
            print(f"平均TOPIXリターン: {sum(topix_returns) / len(topix_returns):.2f}%")
        if excess_returns:
            mean_excess = sum(excess_returns) / len(excess_returns)
            print(f"平均超過リターン: {mean_excess:.2f}%")
        if win_rates:
            mean_win_rate = sum(win_rates) / len(win_rates)
            print(f"平均勝率: {mean_win_rate:.2%}")
        if sharpe_ratios:
            mean_sharpe = sum(sharpe_ratios) / len(sharpe_ratios)
            print(f"平均シャープレシオ: {mean_sharpe:.2f}")
        
        # 最適化時の目的関数値を計算
        if excess_returns and win_rates and sharpe_ratios:
            objective_value = (
                mean_excess * 0.7
                + mean_win_rate * 10.0 * 0.2
                + mean_sharpe * 0.1
            )
            print()
            print(f"【最適化目的関数値】")
            print(f"  = 平均超過リターン × 0.7 + 平均勝率 × 10 × 0.2 + 平均シャープレシオ × 0.1")
            print(f"  = {mean_excess:.2f} × 0.7 + {mean_win_rate:.2%} × 10 × 0.2 + {mean_sharpe:.2f} × 0.1")
            print(f"  = {objective_value:.4f}")
            print()
            print(f"最適化時の最良値: {optimization_result['best_value']:.4f}")
            print(f"今回のバックテスト値: {objective_value:.4f}")
            print(f"差分: {objective_value - optimization_result['best_value']:.4f}")
        
        print()
        print("=" * 80)
        print("詳細な結果はデータベースの backtest_performance テーブルを確認してください")
        print("=" * 80)
    else:
        print("⚠️ 計算されたパフォーマンス結果がありませんでした。")


def main():
    """メイン処理"""
    # 最適化結果ファイル
    result_file = "optimization_result_optimization_20251229_212329.json"
    
    if not Path(result_file).exists():
        print(f"❌ 最適化結果ファイルが見つかりません: {result_file}")
        sys.exit(1)
    
    # 最適化結果を読み込む
    optimization_result = load_optimization_result(result_file)
    
    # 最適化と同じ期間でポートフォリオを作成
    start_date = "2021-01-02"
    end_date = "2025-12-26"
    
    create_portfolio_with_optimized_params(
        start_date=start_date,
        end_date=end_date,
        optimization_result=optimization_result,
    )


if __name__ == "__main__":
    main()







