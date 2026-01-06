"""
最適化結果のパラメータでバックテストを実行

最適化と同じ条件（2022-01-01 ～ 2025-12-28）でポートフォリオを作成し、
バックテストを実行します。

使用方法:
    python run_optimized_backtest.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import List, Optional
import pandas as pd

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.longterm_run import (
    build_features,
    select_portfolio,
    save_features,
    save_portfolio,
)
from omanta_3rd.jobs.batch_longterm_run import get_monthly_rebalance_dates
from omanta_3rd.backtest.performance import (
    calculate_portfolio_performance,
    calculate_all_portfolios_performance,
    save_performance_to_db,
)


def main():
    """最適化結果のパラメータでバックテストを実行"""
    # 最適化時の条件
    start_date = "2022-01-01"
    end_date = "2025-12-28"
    as_of_date = None  # 最新の価格データを使用
    
    print("=" * 80)
    print("最適化結果パラメータでのバックテスト実行")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"評価日: 最新")
    print("=" * 80)
    print()
    
    # リバランス日を取得
    print("リバランス日を取得中...")
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"リバランス日数: {len(rebalance_dates)}")
    print(f"最初: {rebalance_dates[0] if rebalance_dates else 'N/A'}")
    print(f"最後: {rebalance_dates[-1] if rebalance_dates else 'N/A'}")
    print()
    
    if not rebalance_dates:
        print("❌ リバランス日が見つかりませんでした")
        return
    
    # 各リバランス日でポートフォリオを作成
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
                
                # ポートフォリオを選定
                portfolio = select_portfolio(feat)
                
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
    
    try:
        results = calculate_all_portfolios_performance(as_of_date)
        
        # エラーを除外
        valid_results = [r for r in results if "error" not in r]
        
        if not valid_results:
            print("❌ 有効なパフォーマンス結果がありません")
            return
        
        # 各結果を個別に保存
        saved_count = 0
        for perf in valid_results:
            try:
                save_performance_to_db(perf)
                saved_count += 1
            except Exception as e:
                print(f"  ⚠️  パフォーマンス保存エラー ({perf.get('rebalance_date', 'N/A')}): {e}")
        
        print(f"✅ パフォーマンス結果をデータベースに保存しました（{saved_count}/{len(valid_results)}件）")
        print()
        
        # 統計を表示
        print("=" * 80)
        print("【バックテスト結果サマリー】")
        print("=" * 80)
        
        # 各指標の平均を計算
        total_returns = [r.get("total_return_pct", 0) for r in valid_results if r.get("total_return_pct") is not None]
        topix_returns = [
            r.get("topix_comparison", {}).get("topix_return_pct", 0)
            for r in valid_results
            if r.get("topix_comparison", {}).get("topix_return_pct") is not None
        ]
        excess_returns = [
            r.get("topix_comparison", {}).get("excess_return_pct", 0)
            for r in valid_results
            if r.get("topix_comparison", {}).get("excess_return_pct") is not None
        ]
        win_rates = [
            r.get("topix_comparison", {}).get("win_rate", 0)
            for r in valid_results
            if r.get("topix_comparison", {}).get("win_rate") is not None
        ]
        sharpe_ratios = [r.get("sharpe_ratio", 0) for r in valid_results if r.get("sharpe_ratio") is not None]
        
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
        
        print()
        
        # 最適化時の目的関数値を計算
        if excess_returns and win_rates and sharpe_ratios:
            objective_value = (
                mean_excess * 0.7
                + mean_win_rate * 10.0 * 0.2
                + mean_sharpe * 0.1
            )
            print(f"【最適化目的関数値】")
            print(f"  = 平均超過リターン × 0.7 + 平均勝率 × 10 × 0.2 + 平均シャープレシオ × 0.1")
            print(f"  = {mean_excess:.2f} × 0.7 + {mean_win_rate:.2%} × 10 × 0.2 + {mean_sharpe:.2f} × 0.1")
            print(f"  = {objective_value:.4f}")
            print()
            print(f"最適化時の最良値: 4.8551")
            print(f"今回のバックテスト値: {objective_value:.4f}")
            print(f"差分: {objective_value - 4.8551:.4f}")
        
        print()
        print("=" * 80)
        print("詳細な結果はデータベースの backtest_performance テーブルを確認してください")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ パフォーマンス計算エラー: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()

