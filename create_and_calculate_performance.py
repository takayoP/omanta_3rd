"""
更新されたパラメータでポートフォリオを作成し、パフォーマンスを計算

最適化期間（2021-01-02～2025-12-26）でポートフォリオを作成し、
パフォーマンスを計算します。
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
)
from omanta_3rd.jobs.batch_monthly_run import get_monthly_rebalance_dates
from omanta_3rd.backtest.performance import (
    calculate_portfolio_performance,
    save_performance_to_db,
)


def main(start_date: str, end_date: str):
    """ポートフォリオを作成し、パフォーマンスを計算"""
    print("=" * 80)
    print("ポートフォリオ作成とパフォーマンス計算")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print("=" * 80)
    print()

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
                save_portfolio(conn, portfolio)
                print(f"  ✅ ポートフォリオ作成完了: {len(portfolio)}銘柄")
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
            print(f"最適化時の最良値: 8.2627")
            print(f"今回のバックテスト値: {objective_value:.4f}")
            print(f"差分: {objective_value - 8.2627:.4f}")

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

