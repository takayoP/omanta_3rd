"""
固定ホライズン版 seed耐性テスト実行スクリプト（Python）
12M/24M/36Mの各ホライズンでテストを実行します。

Usage:
    python run_fixed_horizon_tests.py
"""

import subprocess
import sys

def main():
    json_file = "optimization_result_optimization_longterm_studyC_20260102_205614.json"
    start_date = "2020-01-01"
    end_date = "2022-12-31"
    n_seeds = 20
    train_ratio = 0.8
    
    horizons = [12, 24, 36]
    
    print("=" * 80)
    print("固定ホライズン版 seed耐性テスト実行")
    print("=" * 80)
    print()
    
    for horizon in horizons:
        print()
        print("=" * 80)
        print(f"ホライズン {horizon}M のテストを実行します...")
        print("=" * 80)
        print()
        
        output_file = f"seed_robustness_fixed_horizon_{horizon}M.json"
        
        cmd = [
            sys.executable,
            "test_seed_robustness_fixed_horizon.py",
            "--json-file", json_file,
            "--start", start_date,
            "--end", end_date,
            "--horizon", str(horizon),
            "--n-seeds", str(n_seeds),
            "--train-ratio", str(train_ratio),
            "--output", output_file,
        ]
        
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print()
            print(f"✓ ホライズン {horizon}M のテストが完了しました")
            print()
        else:
            print()
            print(f"✗ ホライズン {horizon}M のテストでエラーが発生しました")
            print(f"エラーコード: {result.returncode}")
            print()
            sys.exit(1)
    
    print()
    print("=" * 80)
    print("すべてのホライズンテストが完了しました")
    print("=" * 80)
    print()
    print("結果ファイル:")
    for horizon in horizons:
        output_file = f"seed_robustness_fixed_horizon_{horizon}M.json"
        print(f"  - {output_file}")


if __name__ == "__main__":
    main()

