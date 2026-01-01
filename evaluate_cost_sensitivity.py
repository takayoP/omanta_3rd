"""コスト感度テストスクリプト

複数のコストレベル（10bps, 20bpsなど）でHoldout評価を実行し、
コストの影響を分析します。

Usage:
    python evaluate_cost_sensitivity.py --candidates candidates_studyB_20251231_174014.json --cost-levels 0 10 20 30
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import subprocess
import time

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime


def run_holdout_evaluation(
    candidates_file: str,
    holdout_start: str,
    holdout_end: str,
    cost_bps: float,
    output_file: str,
    n_jobs: int = -1,
    use_cache: bool = True,
    cache_dir: str = "cache/features",
) -> Dict[str, Any]:
    """
    Holdout評価を実行
    
    Returns:
        評価結果の辞書（JSONファイルから読み込んだ内容）
    """
    cmd = [
        "python",
        "evaluate_candidates_holdout.py",
        "--candidates", candidates_file,
        "--holdout-start", holdout_start,
        "--holdout-end", holdout_end,
        "--cost-bps", str(cost_bps),
        "--output", output_file,
        "--n-jobs", str(n_jobs),
    ]
    
    if use_cache:
        cmd.extend(["--use-cache", "--cache-dir", cache_dir])
    
    print(f"実行中: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Holdout評価が失敗しました（exit code: {result.returncode}）")
    
    # 結果を読み込む
    with open(output_file, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_cost_sensitivity(results_by_cost: Dict[float, Dict[str, Any]]) -> Dict[str, Any]:
    """
    コスト感度分析を実行
    
    Args:
        results_by_cost: {cost_bps: result_dict} の辞書
                         cost_bpsは片道bps（月次コストは往復=2×片道として計算）
    
    Returns:
        分析結果の辞書
    """
    analysis = {
        "summary_by_cost": {},
        "candidate_rankings": {},
    }
    
    # 各コストレベルでのサマリー
    for cost_bps, result_data in sorted(results_by_cost.items()):
        results = result_data.get("results", [])
        
        if not results:
            continue
        
        # 各候補のSharpe_excess、CAGR_excess、MaxDDを取得
        sharpe_values = []
        sharpe_after_cost_values = []
        cagr_values = []
        maxdd_values = []
        for r in results:
            if "holdout_metrics" in r:
                metrics = r["holdout_metrics"]
                sharpe = metrics.get("sharpe_ratio", None)
                sharpe_after_cost = metrics.get("sharpe_excess_after_cost", None)
                cagr = metrics.get("cagr_excess", None)
                maxdd = metrics.get("max_drawdown", None)
                
                if sharpe is not None:
                    sharpe_values.append(sharpe)
                if sharpe_after_cost is not None:
                    sharpe_after_cost_values.append(sharpe_after_cost)
                if cagr is not None:
                    cagr_values.append(cagr)
                if maxdd is not None:
                    maxdd_values.append(maxdd)
        
        if sharpe_values:
            analysis["summary_by_cost"][cost_bps] = {
                "n_candidates": len(sharpe_values),
                "sharpe_mean": sum(sharpe_values) / len(sharpe_values),
                "sharpe_median": sorted(sharpe_values)[len(sharpe_values) // 2],
                "sharpe_max": max(sharpe_values),
                "sharpe_min": min(sharpe_values),
                "sharpe_after_cost_mean": (
                    sum(sharpe_after_cost_values) / len(sharpe_after_cost_values)
                    if sharpe_after_cost_values else None
                ),
                "cagr_mean": (
                    sum(cagr_values) / len(cagr_values)
                    if cagr_values else None
                ),
                "cagr_median": (
                    sorted(cagr_values)[len(cagr_values) // 2]
                    if cagr_values else None
                ),
                "maxdd_mean": (
                    sum(maxdd_values) / len(maxdd_values)
                    if maxdd_values else None
                ),
                "maxdd_median": (
                    sorted(maxdd_values)[len(maxdd_values) // 2]
                    if maxdd_values else None
                ),
            }
    
    # 各候補のコスト感度分析
    # まず全候補のtrial_numberを収集
    all_trial_numbers = set()
    for result_data in results_by_cost.values():
        results = result_data.get("results", [])
        for r in results:
            all_trial_numbers.add(r.get("trial_number"))
    
        # 各候補についてコスト別のSharpe、CAGR、MaxDDを集計
        for trial_number in sorted(all_trial_numbers):
            candidate_data = {
                "trial_number": trial_number,
                "sharpe_by_cost": {},
                "sharpe_after_cost_by_cost": {},
                "cagr_by_cost": {},
                "maxdd_by_cost": {},
            }
            
            for cost_bps, result_data in sorted(results_by_cost.items()):
                results = result_data.get("results", [])
                for r in results:
                    if r.get("trial_number") == trial_number:
                        if "holdout_metrics" in r:
                            metrics = r["holdout_metrics"]
                            sharpe = metrics.get("sharpe_ratio", None)
                            sharpe_after_cost = metrics.get("sharpe_excess_after_cost", None)
                            cagr = metrics.get("cagr_excess", None)
                            maxdd = metrics.get("max_drawdown", None)
                            
                            candidate_data["sharpe_by_cost"][cost_bps] = sharpe
                            candidate_data["sharpe_after_cost_by_cost"][cost_bps] = sharpe_after_cost
                            candidate_data["cagr_by_cost"][cost_bps] = cagr
                            candidate_data["maxdd_by_cost"][cost_bps] = maxdd
                        break
            
            if candidate_data["sharpe_by_cost"]:
                analysis["candidate_rankings"][trial_number] = candidate_data
    
    return analysis


def print_cost_sensitivity_report(analysis: Dict[str, Any]):
    """
    コスト感度レポートを表示
    """
    print("=" * 80)
    print("コスト感度分析レポート")
    print("=" * 80)
    print()
    
    # bpsの定義を明記
    print("【重要】コストの定義:")
    print("  - 入力cost_bps: 片道（1回の取引あたり）")
    print("  - 月次コスト: 往復 = 2 × 片道（売却 + 購入）")
    print("  - 例: cost_bps=10（片道）の場合、月次コスト = 20 bps（往復）")
    print()
    print("=" * 80)
    print()
    
    # コスト別サマリー
    print("【コスト別サマリー】")
    print("（コストは片道bps、月次コストは往復として計算）")
    print()
    print(f"{'コスト(bps)':<12} {'月次コスト(bps)':<18} {'候補数':<8} {'Sharpe平均':<12} {'Sharpe中央値':<12} {'Sharpe最大':<12} {'Sharpe最小':<12} {'Sharpe(コスト後)平均':<20}")
    print("-" * 120)
    
    summary_by_cost = analysis.get("summary_by_cost", {})
    for cost_bps in sorted(summary_by_cost.keys()):
        summary = summary_by_cost[cost_bps]
        sharpe_after_cost_mean = summary.get("sharpe_after_cost_mean")
        sharpe_after_cost_str = f"{sharpe_after_cost_mean:.4f}" if sharpe_after_cost_mean is not None else "N/A"
        
        # 月次コスト（往復）= 2 × 片道
        monthly_cost_round_trip = cost_bps * 2
        
        print(
            f"{cost_bps:<12.0f} "
            f"{monthly_cost_round_trip:<18.0f} "
            f"{summary['n_candidates']:<8} "
            f"{summary['sharpe_mean']:<12.4f} "
            f"{summary['sharpe_median']:<12.4f} "
            f"{summary['sharpe_max']:<12.4f} "
            f"{summary['sharpe_min']:<12.4f} "
            f"{sharpe_after_cost_str:<20}"
        )
    
    print()
    print("=" * 80)
    print()
    
    # 上位候補のコスト感度
    print("【上位候補のコスト感度（Sharpe > 0.40）】")
    print()
    
    candidate_rankings = analysis.get("candidate_rankings", {})
    
    # コスト0でのSharpeでソート
    candidates_with_sharpe = []
    for trial_number, candidate_data in candidate_rankings.items():
        sharpe_by_cost = candidate_data.get("sharpe_by_cost", {})
        if 0.0 in sharpe_by_cost and sharpe_by_cost[0.0] is not None:
            if sharpe_by_cost[0.0] > 0.40:
                candidates_with_sharpe.append((trial_number, sharpe_by_cost[0.0], candidate_data))
    
    candidates_with_sharpe.sort(key=lambda x: x[1], reverse=True)
    
    if candidates_with_sharpe:
        cost_levels = sorted(summary_by_cost.keys())
        print(f"{'Trial#':<10} ", end="")
        for cost_bps in cost_levels:
            # 片道bpsを明記
            header_str = f"S({int(cost_bps)}bps片道)"
            print(f"{header_str:<18} ", end="")
        print()
        print("-" * (10 + 18 * len(cost_levels)))
        
        for trial_number, sharpe_0, candidate_data in candidates_with_sharpe[:10]:
            print(f"#{trial_number:<9} ", end="")
            sharpe_by_cost = candidate_data.get("sharpe_by_cost", {})
            for cost_bps in cost_levels:
                sharpe = sharpe_by_cost.get(cost_bps, None)
                sharpe_str = f"{sharpe:.4f}" if sharpe is not None else "N/A"
                print(f"{sharpe_str:<15} ", end="")
            print()
    else:
        print("該当する候補が見つかりませんでした。")
    
    print()
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="コスト感度テスト")
    parser.add_argument("--candidates", type=str, required=True, help="候補群のJSONファイルパス")
    parser.add_argument("--holdout-start", type=str, default="2023-01-01", help="Holdout期間の開始日（YYYY-MM-DD）")
    parser.add_argument("--holdout-end", type=str, default="2024-12-31", help="Holdout期間の終了日（YYYY-MM-DD）")
    parser.add_argument("--cost-levels", type=float, nargs="+", default=[0, 10, 20, 30], 
                        help="コストレベル（片道bps）のリスト（デフォルト: 0 10 20 30）。月次コストは往復（2×片道）として計算されます")
    parser.add_argument("--add-slippage", action="store_true", 
                        help="スリッページ/インパクトを考慮（各コストレベルに+5bpsを追加）")
    parser.add_argument("--output-dir", type=str, default="holdout_cost_sensitivity", 
                        help="出力ディレクトリ（デフォルト: holdout_cost_sensitivity）")
    parser.add_argument("--n-jobs", type=int, default=-1, help="並列実行数（-1でCPU数、デフォルト: -1）")
    parser.add_argument("--use-cache", action="store_true", default=True, help="FeatureCacheを使用（デフォルト: True）")
    parser.add_argument("--cache-dir", type=str, default="cache/features", help="キャッシュディレクトリ")
    
    args = parser.parse_args()
    
    # 出力ディレクトリを作成
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # タイムスタンプを取得
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # スリッページシナリオを追加
    cost_levels_final = list(args.cost_levels)
    if args.add_slippage:
        # 各コストレベルに+5bps（片道）を追加
        slippage_levels = [c + 5.0 for c in args.cost_levels if c > 0]  # 0bpsは除外
        cost_levels_final.extend(slippage_levels)
        cost_levels_final = sorted(set(cost_levels_final))  # 重複除去してソート
    
    print("=" * 80)
    print("コスト感度テスト")
    print("=" * 80)
    print(f"候補ファイル: {args.candidates}")
    print(f"Holdout期間: {args.holdout_start} ～ {args.holdout_end}")
    print(f"コストレベル（片道bps）: {cost_levels_final}")
    print(f"  基本レベル: {args.cost_levels}")
    if args.add_slippage:
        print(f"  スリッページ考慮（+5bps）: {[c + 5.0 for c in args.cost_levels if c > 0]}")
    print(f"注意: 月次コストは往復（2×片道）として計算されます")
    print(f"出力ディレクトリ: {output_dir}")
    print("=" * 80)
    print()
    
    # 各コストレベルでHoldout評価を実行
    results_by_cost = {}
    
    for cost_bps in sorted(cost_levels_final):
        print(f"コストレベル {cost_bps} bps の評価を開始...")
        print()
        
        output_file = output_dir / f"holdout_cost_{cost_bps}bps_{timestamp}.json"
        
        try:
            result = run_holdout_evaluation(
                candidates_file=args.candidates,
                holdout_start=args.holdout_start,
                holdout_end=args.holdout_end,
                cost_bps=cost_bps,
                output_file=str(output_file),
                n_jobs=args.n_jobs,
                use_cache=args.use_cache,
                cache_dir=args.cache_dir,
            )
            
            results_by_cost[cost_bps] = result
            print(f"✅ コストレベル {cost_bps} bps の評価が完了しました")
            print()
        except Exception as e:
            print(f"❌ コストレベル {cost_bps} bps の評価が失敗しました: {e}")
            print()
            continue
    
    if not results_by_cost:
        print("❌ 評価結果がありません。終了します。")
        return
    
    # コスト感度分析を実行
    print("コスト感度分析を実行中...")
    print()
    
    analysis = analyze_cost_sensitivity(results_by_cost)
    
    # レポートを表示
    print_cost_sensitivity_report(analysis)
    
    # 分析結果を保存
    analysis_file = output_dir / f"cost_sensitivity_analysis_{timestamp}.json"
    
    # 分析結果に各コストレベルの結果ファイルパスを含める
    analysis["config"] = {
        "candidates_file": args.candidates,
        "holdout_start": args.holdout_start,
        "holdout_end": args.holdout_end,
        "cost_levels": cost_levels_final,
        "cost_levels_base": args.cost_levels,
        "add_slippage": args.add_slippage,
        "note": "cost_levelsは片道bps。月次コストは往復（2×片道）として計算",
        "result_files": {
            cost_bps: str(output_dir / f"holdout_cost_{cost_bps}bps_{timestamp}.json")
            for cost_bps in results_by_cost.keys()
        },
    }
    
    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 分析結果を {analysis_file} に保存しました")
    print()


if __name__ == "__main__":
    main()

