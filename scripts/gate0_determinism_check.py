"""
Gate 0: 決定性チェック

同じseedで2回実行し、結果が一致するか確認します。
ここがズレるなら「探索が不安定」ではなく実装が非決定的（並列・tie-break・共有状態）の可能性があります。
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import time

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def run_optimization_with_seed(
    seed: int,
    initial_params_json: Path,
    output_dir: Path,
    n_trials: int = 100,
    n_jobs: int = 1,
    bt_workers: int = 1,
) -> dict:
    """指定されたseedで最適化を実行し、結果を返す"""
    print(f"\n{'=' * 80}")
    print(f"【Seed {seed} で最適化実行中...】")
    print(f"   n_jobs={n_jobs}, bt_workers={bt_workers}")
    print(f"{'=' * 80}\n")
    
    # 実行開始時刻を記録
    execution_start_time = time.time()
    
    # コマンドを構築
    cmd = [
        sys.executable,
        "-m", "omanta_3rd.jobs.optimize_longterm",
        "--start", "2018-01-31",
        "--end", "2024-12-31",
        "--study-type", "A_local",
        "--n-trials", str(n_trials),
        "--train-end-date", "2023-12-31",
        "--as-of-date", "2024-12-31",
        "--horizon-months", "24",
        "--lambda-penalty", "0.00",
        "--objective-type", "mean",
        "--n-jobs", str(n_jobs),
        "--bt-workers", str(bt_workers),
        "--random-seed", str(seed),
        "--initial-params-json", str(initial_params_json),
    ]
    
    print(f"実行コマンド: {' '.join(cmd)}\n")
    
    # 最適化を実行
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        
        # 実行終了時刻を記録
        execution_end_time = time.time()
        execution_duration = execution_end_time - execution_start_time
        
        # 標準出力から結果ファイル名を探す
        output_lines = result.stdout.split("\n")
        result_file = None
        for line in output_lines:
            if "最適化結果を保存:" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    result_file = Path(parts[-1].strip())
                    if result_file.exists():
                        break
        
        # 見つからない場合は、実行後に作成された最新のファイルを探す
        if result_file is None or not result_file.exists():
            result_dir = Path(".")
            pattern = "optimization_result_optimization_longterm_studyA_local_*.json"
            matching_files = [
                f for f in result_dir.glob(pattern)
                if f.stat().st_mtime >= execution_start_time
            ]
            
            if matching_files:
                result_file = max(matching_files, key=lambda p: p.stat().st_mtime)
            else:
                matching_files = list(result_dir.glob(pattern))
                if matching_files:
                    result_file = max(matching_files, key=lambda p: p.stat().st_mtime)
        
        if result_file is None or not result_file.exists():
            print(f"❌ エラー: 結果ファイルが見つかりません")
            print(f"   標準出力:\n{result.stdout}")
            print(f"   標準エラー:\n{result.stderr}")
            return None
        
        # 結果を読み込む
        with open(result_file, "r", encoding="utf-8") as f:
            result_data = json.load(f)
        
        best_trial = result_data.get("best_trial", {})
        test_perf = result_data.get("test_performance", {})
        
        best_value = best_trial.get("value", 0.0)
        best_params = best_trial.get("params", {})
        mean_excess = test_perf.get("mean_annual_excess_return_pct", 0.0)
        median_excess = test_perf.get("median_annual_excess_return_pct", 0.0)
        win_rate = test_perf.get("win_rate", 0.0)
        num_portfolios = test_perf.get("num_portfolios", 0)
        
        print(f"✅ Seed {seed} 完了（実行時間: {execution_duration:.1f}秒）")
        print(f"   Train最良値: {best_value:.4f}%")
        print(f"   Test平均超過リターン: {mean_excess:.4f}%")
        print(f"   Test中央値超過リターン: {median_excess:.4f}%")
        print(f"   勝率: {win_rate:.4f}")
        print(f"   ポートフォリオ数: {num_portfolios}")
        print(f"   結果ファイル: {result_file}")
        
        return {
            "seed": seed,
            "result_file": str(result_file),
            "best_value": best_value,
            "best_params": best_params,
            "mean_annual_excess_return_pct": mean_excess,
            "median_annual_excess_return_pct": median_excess,
            "win_rate": win_rate,
            "num_portfolios": num_portfolios,
            "execution_duration": execution_duration,
        }
        
    except subprocess.CalledProcessError as e:
        print(f"❌ エラー: 最適化の実行に失敗しました")
        print(f"   リターンコード: {e.returncode}")
        print(f"   標準出力:\n{e.stdout}")
        print(f"   標準エラー:\n{e.stderr}")
        return None
    except Exception as e:
        print(f"❌ エラー: {e}")
        return None


def compare_results(result1: dict, result2: dict, tolerance: float = 0.05) -> dict:
    """2つの結果を比較"""
    comparison = {
        "best_value_diff": abs(result1["best_value"] - result2["best_value"]),
        "mean_excess_diff": abs(result1["mean_annual_excess_return_pct"] - result2["mean_annual_excess_return_pct"]),
        "median_excess_diff": abs(result1["median_annual_excess_return_pct"] - result2["median_annual_excess_return_pct"]),
        "win_rate_diff": abs(result1["win_rate"] - result2["win_rate"]),
        "params_match": result1["best_params"] == result2["best_params"],
    }
    
    # 判定
    comparison["best_value_pass"] = comparison["best_value_diff"] <= tolerance
    comparison["mean_excess_pass"] = comparison["mean_excess_diff"] <= tolerance
    comparison["median_excess_pass"] = comparison["median_excess_diff"] <= tolerance
    comparison["win_rate_pass"] = comparison["win_rate_diff"] <= 0.01  # 勝率は0.01以内
    
    comparison["overall_pass"] = (
        comparison["best_value_pass"] and
        comparison["mean_excess_pass"] and
        comparison["median_excess_pass"] and
        comparison["win_rate_pass"]
    )
    
    return comparison


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gate 0: 決定性チェック")
    parser.add_argument("--initial-params-json", type=str, required=True,
                       help="初期パラメータJSONファイルのパス（1/21のbest_params）")
    parser.add_argument("--seed", type=int, default=42,
                       help="評価するseed（デフォルト: 42）")
    parser.add_argument("--n-trials", type=int, default=100,
                       help="各実行での試行回数（デフォルト: 100）")
    parser.add_argument("--n-jobs", type=int, default=1,
                       help="Optunaの並列数（デフォルト: 1、決定性チェックのため）")
    parser.add_argument("--bt-workers", type=int, default=1,
                       help="バックテストの並列数（デフォルト: 1、決定性チェックのため）")
    parser.add_argument("--tolerance", type=float, default=0.05,
                       help="許容される差（%ポイント、デフォルト: 0.05）")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Gate 0: 決定性チェック")
    print("=" * 80)
    print()
    print("同じseedで2回実行し、結果が一致するか確認します。")
    print("ここがズレるなら「探索が不安定」ではなく実装が非決定的の可能性があります。")
    print()
    
    # 初期パラメータJSONを確認
    initial_params_json = Path(args.initial_params_json)
    if not initial_params_json.exists():
        print(f"❌ エラー: {initial_params_json} が見つかりません")
        return 1
    
    print(f"📄 初期パラメータ: {initial_params_json}")
    print(f"🌱 Seed: {args.seed}")
    print(f"   各実行での試行回数: {args.n_trials}")
    print(f"   n_jobs: {args.n_jobs}（決定性チェックのため）")
    print(f"   bt_workers: {args.bt_workers}（決定性チェックのため）")
    print(f"   許容される差: ±{args.tolerance}%ポイント")
    print()
    
    # 出力ディレクトリを確認
    output_dir = Path(".")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1回目を実行
    print("=" * 80)
    print("【1回目の実行】")
    print("=" * 80)
    result1 = run_optimization_with_seed(
        seed=args.seed,
        initial_params_json=initial_params_json,
        output_dir=output_dir,
        n_trials=args.n_trials,
        n_jobs=args.n_jobs,
        bt_workers=args.bt_workers,
    )
    
    if result1 is None:
        print("❌ エラー: 1回目の実行に失敗しました")
        return 1
    
    print()
    print("=" * 80)
    print("【2回目の実行】")
    print("=" * 80)
    result2 = run_optimization_with_seed(
        seed=args.seed,
        initial_params_json=initial_params_json,
        output_dir=output_dir,
        n_trials=args.n_trials,
        n_jobs=args.n_jobs,
        bt_workers=args.bt_workers,
    )
    
    if result2 is None:
        print("❌ エラー: 2回目の実行に失敗しました")
        return 1
    
    # 結果を比較
    print()
    print("=" * 80)
    print("【結果比較】")
    print("=" * 80)
    print()
    
    comparison = compare_results(result1, result2, tolerance=args.tolerance)
    
    print(f"{'指標':<30} {'1回目':<15} {'2回目':<15} {'差分':<15} {'判定'}")
    print("-" * 80)
    
    print(f"{'Train最良値':<30} {result1['best_value']:<15.4f} {result2['best_value']:<15.4f} {comparison['best_value_diff']:<15.4f} {'✅' if comparison['best_value_pass'] else '❌'}")
    print(f"{'Test平均超過リターン':<30} {result1['mean_annual_excess_return_pct']:<15.4f} {result2['mean_annual_excess_return_pct']:<15.4f} {comparison['mean_excess_diff']:<15.4f} {'✅' if comparison['mean_excess_pass'] else '❌'}")
    print(f"{'Test中央値超過リターン':<30} {result1['median_annual_excess_return_pct']:<15.4f} {result2['median_annual_excess_return_pct']:<15.4f} {comparison['median_excess_diff']:<15.4f} {'✅' if comparison['median_excess_pass'] else '❌'}")
    print(f"{'勝率':<30} {result1['win_rate']:<15.4f} {result2['win_rate']:<15.4f} {comparison['win_rate_diff']:<15.4f} {'✅' if comparison['win_rate_pass'] else '❌'}")
    print(f"{'パラメータ一致':<30} {'-':<15} {'-':<15} {'-':<15} {'✅' if comparison['params_match'] else '❌'}")
    
    print()
    
    # 判定
    print("=" * 80)
    print("【判定】")
    print("=" * 80)
    print()
    
    if comparison["overall_pass"]:
        print("✅ Gate 0: PASS")
        print(f"   同じseedで2回実行した結果が一致しています（差分: {comparison['mean_excess_diff']:.4f}%ポイント）")
        print(f"   実装は決定的であり、今回のGate 1のぶれは「探索の到達ブレ」の可能性が高いです")
        return 0
    else:
        print("❌ Gate 0: FAIL")
        print(f"   同じseedで2回実行した結果が一致しません（差分: {comparison['mean_excess_diff']:.4f}%ポイント）")
        print(f"   実装が非決定的（並列・tie-break・共有状態）の可能性があります")
        print(f"   本番反映前に、実装の決定性を確保してください")
        return 1


if __name__ == "__main__":
    sys.exit(main())
