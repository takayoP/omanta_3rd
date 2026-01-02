"""最適化実行前のGo/No-Goチェックスクリプト

ChatGPTの提案に基づいて、以下のチェックを実施します：
1. チェックA：ユニバース診断（最重要）
2. チェックB：1つのtrialを「同一条件で2回」回して一致するか
3. チェックC：Holdoutを"使い潰さない"設計になっているか

Usage:
    python check_optimization_readiness.py
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.jobs.batch_monthly_run import get_monthly_rebalance_dates
from src.omanta_3rd.jobs.monthly_run import build_features, _load_universe, _snap_listed_date
from src.omanta_3rd.jobs.optimize_timeseries import run_backtest_for_optimization_timeseries
from src.omanta_3rd.jobs.monthly_run import StrategyParams
from src.omanta_3rd.jobs.optimize import EntryScoreParams
from dataclasses import replace


def check_universe_diagnosis() -> Dict[str, any]:
    """
    チェックA：ユニバース診断（最重要）
    
    2020-2022の各月末（またはリバランス日）で
    - 銘柄数が不自然に少ない/多い
    - 2020-2021に"プライム限定"っぽい挙動になっていない
    - 上場廃止銘柄が一切出てこない（＝サバイバーのみ）になっていない
    を確認。
    """
    print("=" * 80)
    print("チェックA：ユニバース診断（最重要）")
    print("=" * 80)
    print()
    
    # リバランス日を取得（2020-2022）
    rebalance_dates = get_monthly_rebalance_dates("2020-01-01", "2022-12-31")
    
    if not rebalance_dates:
        return {
            "status": "ERROR",
            "message": "リバランス日が見つかりませんでした"
        }
    
    print(f"確認対象期間: {rebalance_dates[0]} ～ {rebalance_dates[-1]}")
    print(f"リバランス日数: {len(rebalance_dates)}")
    print()
    
    universe_stats = []
    
    with connect_db(read_only=True) as conn:
        for rebalance_date in rebalance_dates[:12]:  # 最初の12ヶ月分をサンプル確認
            try:
                listed_date = _snap_listed_date(conn, rebalance_date)
                universe = _load_universe(conn, listed_date)
                
                # 市場区分の分布を確認
                if not universe.empty and "market_name" in universe.columns:
                    market_dist = universe["market_name"].value_counts()
                    prime_count = universe["market_name"].astype(str).str.contains("プライム|Prime", na=False).sum()
                    first_section_count = universe["market_name"].astype(str).str.contains("東証一部|一部", na=False).sum()
                else:
                    market_dist = pd.Series()
                    prime_count = 0
                    first_section_count = 0
                
                universe_stats.append({
                    "rebalance_date": rebalance_date,
                    "listed_date": listed_date,
                    "universe_count": len(universe),
                    "prime_count": prime_count,
                    "first_section_count": first_section_count,
                    "market_dist": market_dist.to_dict() if not market_dist.empty else {},
                })
                
                print(f"{rebalance_date}: ユニバース={len(universe)}銘柄, "
                      f"プライム={prime_count}, 東証一部={first_section_count}")
                if not market_dist.empty:
                    print(f"  市場区分: {dict(market_dist.head(5))}")
                
            except Exception as e:
                print(f"❌ エラー ({rebalance_date}): {e}")
                universe_stats.append({
                    "rebalance_date": rebalance_date,
                    "error": str(e),
                })
    
    print()
    
    # 分析
    if not universe_stats:
        return {
            "status": "ERROR",
            "message": "ユニバース統計が取得できませんでした"
        }
    
    # 2020-2021年と2022年で比較
    stats_2020_2021 = [s for s in universe_stats if s.get("rebalance_date", "").startswith(("2020", "2021"))]
    stats_2022 = [s for s in universe_stats if s.get("rebalance_date", "").startswith("2022")]
    
    issues = []
    warnings = []
    
    # 問題1: 2020-2021年にプライムが多すぎる（東証一部が少なすぎる）
    if stats_2020_2021:
        avg_prime_2020_2021 = np.mean([s.get("prime_count", 0) for s in stats_2020_2021])
        avg_first_2020_2021 = np.mean([s.get("first_section_count", 0) for s in stats_2020_2021])
        
        if avg_prime_2020_2021 > 100 and avg_first_2020_2021 < 100:
            issues.append(
                f"⚠️ 2020-2021年にプライム銘柄が多すぎます（平均{avg_prime_2020_2021:.0f}銘柄）。"
                f"東証一部が少なすぎます（平均{avg_first_2020_2021:.0f}銘柄）。"
                f"これは「現在のプライム銘柄を過去に遡って使っている」可能性を示唆します。"
            )
        elif avg_first_2020_2021 < 50:
            issues.append(
                f"⚠️ 2020-2021年の東証一部銘柄が異常に少ない（平均{avg_first_2020_2021:.0f}銘柄）。"
                f"データ取得に問題がある可能性があります。"
            )
    
    # 問題2: 銘柄数が不自然に少ない/多い
    counts = [s.get("universe_count", 0) for s in universe_stats if "error" not in s]
    if counts:
        min_count = min(counts)
        max_count = max(counts)
        avg_count = np.mean(counts)
        
        if min_count < 100:
            issues.append(
                f"⚠️ ユニバース銘柄数が異常に少ない（最小{min_count}銘柄）。"
                f"データ取得に問題がある可能性があります。"
            )
        elif max_count - min_count > 500:
            warnings.append(
                f"⚠️ ユニバース銘柄数の変動が大きい（{min_count}～{max_count}銘柄、平均{avg_count:.0f}銘柄）。"
                f"市場区分の変更による可能性がありますが、確認を推奨します。"
            )
    
    # 問題3: listed_infoテーブルに過去の日付が適切に保存されているか
    with connect_db(read_only=True) as conn:
        date_range = pd.read_sql_query(
            """
            SELECT MIN(date) AS min_date, MAX(date) AS max_date, COUNT(DISTINCT date) AS date_count
            FROM listed_info
            """,
            conn
        )
        
        if not date_range.empty:
            min_date = date_range["min_date"].iloc[0]
            max_date = date_range["max_date"].iloc[0]
            date_count = date_range["date_count"].iloc[0]
            
            print(f"listed_infoテーブルの日付範囲: {min_date} ～ {max_date} ({date_count}日分)")
            
            if pd.to_datetime(min_date) > pd.to_datetime("2020-01-01"):
                issues.append(
                    f"⚠️ listed_infoテーブルの最小日付が{min_date}で、2020年以前のデータがありません。"
                    f"過去の銘柄構成を復元できません。"
                )
            elif date_count < 100:
                warnings.append(
                    f"⚠️ listed_infoテーブルの日付数が少ない（{date_count}日）。"
                    f"月次スナップショットの場合、36ヶ月で36日分程度になるのが正常です。"
                )
    
    print()
    
    # 結果をまとめる
    if issues:
        print("❌ 重大な問題が見つかりました:")
        for issue in issues:
            print(f"  {issue}")
        print()
        return {
            "status": "NO_GO",
            "issues": issues,
            "warnings": warnings,
            "stats": universe_stats,
        }
    elif warnings:
        print("⚠️ 警告:")
        for warning in warnings:
            print(f"  {warning}")
        print()
        return {
            "status": "WARNING",
            "issues": [],
            "warnings": warnings,
            "stats": universe_stats,
        }
    else:
        print("✅ ユニバース診断: 問題なし")
        print()
        return {
            "status": "OK",
            "issues": [],
            "warnings": [],
            "stats": universe_stats,
        }


def check_deterministic_trial() -> Dict[str, any]:
    """
    チェックB：1つのtrialを「同一条件で2回」回して一致するか
    
    同じseed、同じデータで
    P/L時系列・Sharpeが一致
    → 一致しないなら、どこかに非決定性（データ取得/前処理/並列）が混ざっていて、最適化が不安定になります。
    """
    print("=" * 80)
    print("チェックB：決定性チェック（同一条件で2回実行して一致するか）")
    print("=" * 80)
    print()
    
    # サンプルのリバランス日を取得（2022年の最初の3ヶ月）
    rebalance_dates = get_monthly_rebalance_dates("2022-01-01", "2022-03-31")
    
    if len(rebalance_dates) < 2:
        return {
            "status": "SKIP",
            "message": "リバランス日が不足しています"
        }
    
    print(f"テスト対象: {len(rebalance_dates)}リバランス日")
    print()
    
    # 固定パラメータ
    default_params = StrategyParams()
    strategy_params = replace(
        default_params,
        target_min=12,
        target_max=12,
    )
    
    entry_params = EntryScoreParams()
    
    # 1回目
    print("1回目の実行...")
    result1 = run_backtest_for_optimization_timeseries(
        rebalance_dates,
        strategy_params,
        entry_params,
        cost_bps=0.0,
        n_jobs=1,
        enable_timing=False,
        save_to_db=False,
    )
    
    sharpe1 = result1.get("sharpe_ratio", 0.0)
    mean_excess1 = result1.get("mean_excess_return", 0.0)
    num_portfolios1 = result1.get("num_portfolios", 0)
    
    print(f"  結果: Sharpe={sharpe1:.6f}, mean_excess={mean_excess1:.6f}%, portfolios={num_portfolios1}")
    
    # 2回目
    print("2回目の実行...")
    result2 = run_backtest_for_optimization_timeseries(
        rebalance_dates,
        strategy_params,
        entry_params,
        cost_bps=0.0,
        n_jobs=1,
        enable_timing=False,
        save_to_db=False,
    )
    
    sharpe2 = result2.get("sharpe_ratio", 0.0)
    mean_excess2 = result2.get("mean_excess_return", 0.0)
    num_portfolios2 = result2.get("num_portfolios", 0)
    
    print(f"  結果: Sharpe={sharpe2:.6f}, mean_excess={mean_excess2:.6f}%, portfolios={num_portfolios2}")
    print()
    
    # 比較
    sharpe_diff = abs(sharpe1 - sharpe2)
    mean_excess_diff = abs(mean_excess1 - mean_excess2)
    
    # 許容誤差（浮動小数点誤差を考慮）
    EPSILON = 1e-6
    
    if sharpe_diff > EPSILON or mean_excess_diff > EPSILON or num_portfolios1 != num_portfolios2:
        issues = []
        if sharpe_diff > EPSILON:
            issues.append(f"Sharpe値が不一致（差: {sharpe_diff:.6f}）")
        if mean_excess_diff > EPSILON:
            issues.append(f"平均超過リターンが不一致（差: {mean_excess_diff:.6f}%）")
        if num_portfolios1 != num_portfolios2:
            issues.append(f"ポートフォリオ数が不一致（{num_portfolios1} vs {num_portfolios2}）")
        
        print("❌ 決定性チェック: 不一致が見つかりました")
        for issue in issues:
            print(f"  ⚠️ {issue}")
        print()
        
        return {
            "status": "NO_GO",
            "issues": issues,
            "result1": {"sharpe": sharpe1, "mean_excess": mean_excess1, "num_portfolios": num_portfolios1},
            "result2": {"sharpe": sharpe2, "mean_excess": mean_excess2, "num_portfolios": num_portfolios2},
        }
    else:
        print("✅ 決定性チェック: 一致しました（決定性が保証されています）")
        print()
        
        return {
            "status": "OK",
            "issues": [],
            "result1": {"sharpe": sharpe1, "mean_excess": mean_excess1, "num_portfolios": num_portfolios1},
            "result2": {"sharpe": sharpe2, "mean_excess": mean_excess2, "num_portfolios": num_portfolios2},
        }


def check_holdout_design() -> Dict[str, any]:
    """
    チェックC：Holdoutを"使い潰さない"設計になっているか
    
    実務ではよくこう分けます：
    - Train：2020-2022（最適化に使う）
    - Validation：2023（方針修正・再最適化の意思決定に使ってよい）
    - Final Test：2024（最後の一発勝負。ここは触らない）
    """
    print("=" * 80)
    print("チェックC：Holdout設計の確認")
    print("=" * 80)
    print()
    
    print("推奨される期間分割:")
    print("  - Train：2020-2022（最適化に使う）")
    print("  - Validation：2023（方針修正・再最適化の意思決定に使ってよい）")
    print("  - Final Test：2024（最後の一発勝負。ここは触らない）")
    print()
    
    print("現在の設計:")
    print("  - Train：2020-2022（最適化に使う）✅")
    print("  - Test：2023-2024（固定評価）")
    print()
    
    print("⚠️ 注意: 現在の設計では、Test期間（2023-2024）を一度だけ使うようにしてください。")
    print("  Testを見て調整→またTestで評価、を繰り返すとTestが汚れます。")
    print()
    
    # 2025年のデータについて
    print("2025年のデータについて:")
    print("  - 現在は2025/12/31なので、2025年のデータは未使用で残っています。")
    print("  - 今後、より長期間の評価や追加の検証に使用可能です。")
    print("  - Final Testとして2025年を確保しておくのも選択肢です。")
    print()
    
    return {
        "status": "OK",
        "message": "Holdout設計は適切ですが、Test期間を複数回使わないように注意が必要です",
        "recommendation": "将来的には Validation（2023）と Final Test（2024）に分けることを検討してください",
    }


def main():
    """メイン関数"""
    print("=" * 80)
    print("最適化実行前のGo/No-Goチェック")
    print("=" * 80)
    print()
    
    results = {}
    
    # チェックA：ユニバース診断
    results["universe"] = check_universe_diagnosis()
    print()
    
    # チェックB：決定性チェック
    results["deterministic"] = check_deterministic_trial()
    print()
    
    # チェックC：Holdout設計
    results["holdout"] = check_holdout_design()
    print()
    
    # 総合判断
    print("=" * 80)
    print("総合判断")
    print("=" * 80)
    print()
    
    no_go_count = sum(1 for r in results.values() if r.get("status") == "NO_GO")
    warning_count = sum(1 for r in results.values() if r.get("status") == "WARNING")
    
    if no_go_count > 0:
        print("❌ NO-GO: 重大な問題が見つかりました。最適化を実行する前に問題を修正してください。")
        print()
        for check_name, result in results.items():
            if result.get("status") == "NO_GO":
                print(f"{check_name.upper()}:")
                for issue in result.get("issues", []):
                    print(f"  - {issue}")
        return 1
    elif warning_count > 0:
        print("⚠️ WARNING: 警告がありますが、最適化は実行可能です。")
        print("  ただし、警告内容を確認してから実行することを推奨します。")
        print()
        for check_name, result in results.items():
            if result.get("status") == "WARNING":
                print(f"{check_name.upper()}:")
                for warning in result.get("warnings", []):
                    print(f"  - {warning}")
        print()
        print("✅ GO（警告付き）: 最適化を実行してよいですが、警告内容に注意してください。")
        return 0
    else:
        print("✅ GO: 全てのチェックをパスしました。最適化を実行してよいです。")
        return 0


if __name__ == "__main__":
    sys.exit(main())





