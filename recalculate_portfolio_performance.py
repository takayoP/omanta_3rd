"""
現在のパラメータ設定でポートフォリオとパフォーマンスを再計算

既存のポートフォリオを削除し、現在のパラメータ設定（12銘柄）で
ポートフォリオを再作成し、パフォーマンスを再計算します。
"""

from __future__ import annotations

import sys
from typing import List, Dict, Any

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.monthly_run import (
    build_features,
    select_portfolio,
    save_features,
    save_portfolio,
    PARAMS,
)
from omanta_3rd.jobs.batch_monthly_run import get_monthly_rebalance_dates
from omanta_3rd.backtest.performance import (
    calculate_portfolio_performance,
    save_performance_to_db,
)


def check_existing_portfolios(start_date: str, end_date: str):
    """既存のポートフォリオを確認"""
    print("=" * 80)
    print("既存のポートフォリオ確認")
    print("=" * 80)
    
    with connect_db() as conn:
        import pandas as pd
        
        # 各リバランス日の銘柄数を確認
        portfolio_counts = pd.read_sql_query(
            """
            SELECT rebalance_date, COUNT(*) as num_stocks
            FROM portfolio_monthly
            WHERE rebalance_date >= ? AND rebalance_date <= ?
            GROUP BY rebalance_date
            ORDER BY rebalance_date
            """,
            conn,
            params=(start_date, end_date),
        )
        
        if portfolio_counts.empty:
            print("指定期間内に既存のポートフォリオはありません。")
            return
        
        print(f"リバランス日数: {len(portfolio_counts)}")
        print()
        print("各リバランス日の銘柄数:")
        for _, row in portfolio_counts.iterrows():
            num_stocks = row["num_stocks"]
            expected = PARAMS.target_max
            status = "✅" if num_stocks == expected else "⚠️"
            print(f"  {status} {row['rebalance_date']}: {num_stocks}銘柄 (期待値: {expected}銘柄)")
        
        # 期待値と異なるポートフォリオを確認
        incorrect = portfolio_counts[portfolio_counts["num_stocks"] != PARAMS.target_max]
        if not incorrect.empty:
            print()
            print(f"⚠️ 期待値と異なるポートフォリオ数: {len(incorrect)}件")
            print(f"   現在の設定: target_min={PARAMS.target_min}, target_max={PARAMS.target_max}")
        else:
            print()
            print("✅ すべてのポートフォリオが期待値と一致しています。")
        
        print()


def clear_portfolios(start_date: str, end_date: str):
    """指定期間のポートフォリオを削除"""
    print("=" * 80)
    print("既存のポートフォリオを削除中...")
    print("=" * 80)
    
    with connect_db() as conn:
        # ポートフォリオを削除
        cursor = conn.execute(
            """
            DELETE FROM portfolio_monthly
            WHERE rebalance_date >= ? AND rebalance_date <= ?
            """,
            (start_date, end_date),
        )
        deleted_portfolios = cursor.rowcount
        
        # パフォーマンスも削除
        cursor = conn.execute(
            """
            DELETE FROM backtest_performance
            WHERE rebalance_date >= ? AND rebalance_date <= ?
            """,
            (start_date, end_date),
        )
        deleted_performance = cursor.rowcount
        
        cursor = conn.execute(
            """
            DELETE FROM backtest_stock_performance
            WHERE rebalance_date >= ? AND rebalance_date <= ?
            """,
            (start_date, end_date),
        )
        deleted_stock_performance = cursor.rowcount
        
        conn.commit()
        
        print(f"削除されたポートフォリオ: {deleted_portfolios}件")
        print(f"削除されたパフォーマンス: {deleted_performance}件")
        print(f"削除された銘柄別パフォーマンス: {deleted_stock_performance}件")
        print()


def main(start_date: str, end_date: str):
    """ポートフォリオを作成し、パフォーマンスを計算"""
    print("=" * 80)
    print("ポートフォリオとパフォーマンスの再計算")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"現在のパラメータ設定:")
    print(f"  target_min: {PARAMS.target_min}")
    print(f"  target_max: {PARAMS.target_max}")
    print(f"  roe_min: {PARAMS.roe_min}")
    print(f"  liquidity_quantile_cut: {PARAMS.liquidity_quantile_cut}")
    print("=" * 80)
    print()
    
    # 既存のポートフォリオを確認
    check_existing_portfolios(start_date, end_date)
    
    # 既存のポートフォリオを削除
    clear_portfolios(start_date, end_date)
    
    # リバランス日を取得
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    if not rebalance_dates:
        print("❌ 指定期間内にリバランス日が見つかりませんでした。")
        return
    
    print(f"リバランス日数: {len(rebalance_dates)}")
    print(f"最初: {rebalance_dates[0]}")
    print(f"最後: {rebalance_dates[-1]}")
    print()
    print("=" * 80)
    print("ポートフォリオ作成中...")
    print("=" * 80)
    
    successful_portfolios = 0
    for i, rebalance_date in enumerate(rebalance_dates, 1):
        print(f"[{i}/{len(rebalance_dates)}] {rebalance_date} のポートフォリオを作成中...")
        try:
            with connect_db() as conn:
                feat = build_features(conn, rebalance_date)
                if feat.empty:
                    print(f"  ⚠️ {rebalance_date}: 特徴量データが空のためスキップします。")
                    continue
                save_features(conn, feat)
                
                portfolio = select_portfolio(feat)
                if portfolio.empty:
                    print(f"  ⚠️ {rebalance_date}: ポートフォリオが空のためスキップします。")
                    continue
                
                # 銘柄数を確認
                num_stocks = len(portfolio)
                expected = PARAMS.target_max
                if num_stocks != expected:
                    print(f"  ⚠️ {rebalance_date}: 銘柄数が期待値と異なります ({num_stocks} != {expected})")
                
                save_portfolio(conn, portfolio)
                print(f"  ✅ ポートフォリオ作成完了: {num_stocks}銘柄")
                successful_portfolios += 1
        except Exception as e:
            print(f"  ❌ エラー ({rebalance_date}): ポートフォリオ作成中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
    
    print()
    print("=" * 80)
    print("ポートフォリオ作成結果")
    print("=" * 80)
    print(f"成功: {successful_portfolios}/{len(rebalance_dates)}")
    print(f"エラー: {len(rebalance_dates) - successful_portfolios}/{len(rebalance_dates)}")
    print()
    
    # 作成されたポートフォリオの銘柄数を再確認
    print("=" * 80)
    print("作成されたポートフォリオの確認")
    print("=" * 80)
    with connect_db() as conn:
        import pandas as pd
        portfolio_counts = pd.read_sql_query(
            """
            SELECT rebalance_date, COUNT(*) as num_stocks
            FROM portfolio_monthly
            WHERE rebalance_date >= ? AND rebalance_date <= ?
            GROUP BY rebalance_date
            ORDER BY rebalance_date
            """,
            conn,
            params=(start_date, end_date),
        )
        
        if not portfolio_counts.empty:
            incorrect = portfolio_counts[portfolio_counts["num_stocks"] != PARAMS.target_max]
            if not incorrect.empty:
                print(f"⚠️ 期待値と異なるポートフォリオ:")
                for _, row in incorrect.iterrows():
                    print(f"  {row['rebalance_date']}: {row['num_stocks']}銘柄 (期待値: {PARAMS.target_max}銘柄)")
            else:
                print(f"✅ すべてのポートフォリオが{PARAMS.target_max}銘柄で作成されました。")
        print()
    
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
                print(f"  ❌ パフォーマンス計算エラー ({rebalance_date}): {perf['error']}")
        except Exception as e:
            print(f"  ❌ エラー ({rebalance_date}): パフォーマンス計算中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
    
    # パフォーマンス結果をデータベースに保存
    if performance_results:
        print(f"✅ パフォーマンス結果をデータベースに保存しました（{len(performance_results)}/{len(rebalance_dates)}件）")
    else:
        print("⚠️ 保存するパフォーマンス結果がありませんでした。")
    
    # サマリー表示
    if performance_results:
        total_returns = [p["total_return_pct"] for p in performance_results if p.get("total_return_pct") is not None]
        topix_returns = [p["topix_comparison"]["topix_return_pct"] for p in performance_results if p.get("topix_comparison", {}).get("topix_return_pct") is not None]
        excess_returns = [p["topix_comparison"]["excess_return_pct"] for p in performance_results if p.get("topix_comparison", {}).get("excess_return_pct") is not None]
        win_rates = [p.get("topix_comparison", {}).get("win_rate") for p in performance_results if p.get("topix_comparison", {}).get("win_rate") is not None]
        sharpe_ratios = [p.get("sharpe_ratio") for p in performance_results if p.get("sharpe_ratio") is not None]
        
        print()
        print("=" * 80)
        print("【バックテスト結果サマリー】")
        print("=" * 80)
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
            sharpe_ratios_valid = [s for s in sharpe_ratios if s is not None]
            if sharpe_ratios_valid:
                mean_sharpe = sum(sharpe_ratios_valid) / len(sharpe_ratios_valid)
                print(f"平均シャープレシオ: {mean_sharpe:.2f}")
        
        print()
        print("=" * 80)
        print("詳細な結果はデータベースの backtest_performance テーブルを確認してください")
        print("=" * 80)
    else:
        print()
        print("⚠️ 計算されたパフォーマンス結果がありませんでした。")


if __name__ == "__main__":
    # 最適化期間と同じ期間を使用
    start_date = "2021-01-02"
    end_date = "2025-12-26"
    main(start_date=start_date, end_date=end_date)

