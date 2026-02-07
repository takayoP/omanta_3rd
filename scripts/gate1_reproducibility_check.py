"""
Gate 1: 再現性チェック

同じ設定でseedを変えて複数回実行し、Test期間の平均超過リターンが極端にブレないことを確認します。
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import statistics

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def run_optimization_with_seed(
    seed: int,
    initial_params_json: Path,
    output_dir: Path,
    n_trials: int = 100,
) -> dict:
    """指定されたseedで最適化を実行し、結果を返す"""
    print(f"\n{'=' * 80}")
    print(f"【Seed {seed} で最適化実行中...】")
    print(f"{'=' * 80}\n")
    
    # 出力ファイル名を生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"optimization_result_seed{seed}_{timestamp}.json"
    
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
        "--n-jobs", "1",
        "--bt-workers", "4",
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
        
        # 標準出力から結果ファイル名を探す
        # 通常は "最適化結果を保存: ..." という行がある
        output_lines = result.stdout.split("\n")
        result_file = None
        for line in output_lines:
            if "最適化結果を保存:" in line:
                # ファイルパスを抽出
                parts = line.split(":")
                if len(parts) > 1:
                    result_file = Path(parts[-1].strip())
                    if result_file.exists():
                        break
        
        # 見つからない場合は、実行直後に作成された最新のoptimization_resultファイルを探す
        if result_file is None or not result_file.exists():
            # 実行開始時刻を記録（実行前のタイムスタンプ）
            import time
            execution_start_time = time.time() - 300  # 5分前から探す（実行時間を考慮）
            
            # 最新のoptimization_resultファイルを探す（studyA_localで、実行後に作成されたもの）
            result_dir = Path(".")
            pattern = "optimization_result_optimization_longterm_studyA_local_*.json"
            matching_files = [
                f for f in result_dir.glob(pattern)
                if f.stat().st_mtime >= execution_start_time
            ]
            
            if matching_files:
                # 最も新しいファイルを選択
                result_file = max(matching_files, key=lambda p: p.stat().st_mtime)
                print(f"   注意: 標準出力から結果ファイル名を抽出できませんでした。")
                print(f"         最新のファイルを使用: {result_file.name}")
            else:
                # 実行前のタイムスタンプを考慮せず、単純に最新のファイルを探す
                matching_files = list(result_dir.glob(pattern))
                if matching_files:
                    result_file = max(matching_files, key=lambda p: p.stat().st_mtime)
                    print(f"   警告: 実行後に作成されたファイルが見つかりませんでした。")
                    print(f"         最新のファイルを使用: {result_file.name}")
                    print(f"         このファイルが今回の実行結果か確認してください。")
        
        if result_file is None or not result_file.exists():
            print(f"❌ エラー: 結果ファイルが見つかりません")
            print(f"   標準出力:\n{result.stdout}")
            print(f"   標準エラー:\n{result.stderr}")
            return None
        
        # 結果を読み込む
        with open(result_file, "r", encoding="utf-8") as f:
            result_data = json.load(f)
        
        test_perf = result_data.get("test_performance", {})
        mean_excess = test_perf.get("mean_annual_excess_return_pct", 0.0)
        median_excess = test_perf.get("median_annual_excess_return_pct", 0.0)
        win_rate = test_perf.get("win_rate", 0.0)
        num_portfolios = test_perf.get("num_portfolios", 0)
        
        print(f"✅ Seed {seed} 完了")
        print(f"   Test平均超過リターン: {mean_excess:.4f}%")
        print(f"   Test中央値超過リターン: {median_excess:.4f}%")
        print(f"   勝率: {win_rate:.4f}")
        print(f"   ポートフォリオ数: {num_portfolios}")
        print(f"   結果ファイル: {result_file}")
        
        return {
            "seed": seed,
            "result_file": str(result_file),
            "mean_annual_excess_return_pct": mean_excess,
            "median_annual_excess_return_pct": median_excess,
            "win_rate": win_rate,
            "num_portfolios": num_portfolios,
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


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gate 1: 再現性チェック")
    parser.add_argument("--initial-params-json", type=str, required=True,
                       help="初期パラメータJSONファイルのパス（1/21のbest_params）")
    parser.add_argument("--seeds", type=str, default="42,123,456,789,999",
                       help="評価するseedのリスト（カンマ区切り、デフォルト: 42,123,456,789,999）")
    parser.add_argument("--n-trials", type=int, default=100,
                       help="各seedでの試行回数（デフォルト: 100）")
    parser.add_argument("--output-dir", type=str, default=".",
                       help="結果ファイルの出力ディレクトリ（デフォルト: カレントディレクトリ）")
    parser.add_argument("--tolerance", type=float, default=1.0,
                       help="許容されるブレ（%ポイント、デフォルト: 1.0）")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Gate 1: 再現性チェック")
    print("=" * 80)
    print()
    print("同じ設定でseedを変えて複数回実行し、")
    print("Test期間の平均超過リターンが極端にブレないことを確認します。")
    print()
    
    # 初期パラメータJSONを確認
    initial_params_json = Path(args.initial_params_json)
    if not initial_params_json.exists():
        print(f"❌ エラー: {initial_params_json} が見つかりません")
        return 1
    
    print(f"📄 初期パラメータ: {initial_params_json}")
    print()
    
    # seedのリストを解析
    seeds = [int(x.strip()) for x in args.seeds.split(",")]
    print(f"🌱 評価するseed: {seeds}")
    print(f"   各seedでの試行回数: {args.n_trials}")
    print(f"   許容されるブレ: ±{args.tolerance}%ポイント")
    print()
    
    # 出力ディレクトリを確認
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 各seedで最適化を実行
    results = []
    
    for seed in seeds:
        result = run_optimization_with_seed(
            seed=seed,
            initial_params_json=initial_params_json,
            output_dir=output_dir,
            n_trials=args.n_trials,
        )
        
        if result is None:
            print(f"❌ Seed {seed} の実行に失敗しました。スキップします。")
            continue
        
        results.append(result)
    
    if len(results) == 0:
        print("❌ エラー: すべてのseedで実行に失敗しました")
        return 1
    
    # 結果サマリー
    print()
    print("=" * 80)
    print("【結果サマリー】")
    print("=" * 80)
    print()
    
    mean_excess_list = [r["mean_annual_excess_return_pct"] for r in results]
    median_excess_list = [r["median_annual_excess_return_pct"] for r in results]
    win_rate_list = [r["win_rate"] for r in results]
    
    print(f"{'Seed':<10} {'平均超過':<12} {'中央値超過':<12} {'勝率':<8} {'結果ファイル'}")
    print("-" * 100)
    
    for r in results:
        seed = r["seed"]
        mean_excess = r["mean_annual_excess_return_pct"]
        median_excess = r["median_annual_excess_return_pct"]
        win_rate = r["win_rate"]
        result_file = Path(r["result_file"]).name
        
        print(f"{seed:<10} {mean_excess:<12.4f} {median_excess:<12.4f} {win_rate:<8.4f} {result_file}")
    
    print()
    print("=" * 80)
    print("【統計サマリー】")
    print("=" * 80)
    print()
    
    mean_mean = statistics.mean(mean_excess_list)
    median_mean = statistics.median(mean_excess_list)
    std_mean = statistics.stdev(mean_excess_list) if len(mean_excess_list) > 1 else 0.0
    min_mean = min(mean_excess_list)
    max_mean = max(mean_excess_list)
    range_mean = max_mean - min_mean
    
    print(f"平均超過リターン（平均）: {mean_mean:.4f}%")
    print(f"平均超過リターン（中央値）: {median_mean:.4f}%")
    print(f"平均超過リターン（標準偏差）: {std_mean:.4f}%")
    print(f"平均超過リターン（最小）: {min_mean:.4f}%")
    print(f"平均超過リターン（最大）: {max_mean:.4f}%")
    print(f"平均超過リターン（範囲）: {range_mean:.4f}%ポイント")
    print()
    
    # 判定
    print("=" * 80)
    print("【判定】")
    print("=" * 80)
    print()
    
    if range_mean <= args.tolerance:
        print(f"✅ Gate 1: PASS")
        print(f"   範囲（{range_mean:.4f}%ポイント）が許容範囲（±{args.tolerance}%ポイント）内です")
        print(f"   探索は安定しており、将来も急変しにくい可能性が高いです")
        return 0
    else:
        print(f"❌ Gate 1: FAIL")
        print(f"   範囲（{range_mean:.4f}%ポイント）が許容範囲（±{args.tolerance}%ポイント）を超えています")
        print(f"   探索が不安定（将来も急変しやすい）可能性があります")
        print(f"   本番反映前に、探索設定の見直しを検討してください")
        return 1


if __name__ == "__main__":
    sys.exit(main())
