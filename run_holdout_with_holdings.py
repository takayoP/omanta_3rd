"""Holdout評価を実行するヘルパースクリプト（ポートフォリオ情報を含む）

このスクリプトは、ポートフォリオ情報と保有銘柄詳細を含むholdout評価を実行します。
"""

import subprocess
import sys
from pathlib import Path

def main():
    """メイン処理"""
    # 候補ファイル
    candidates_file = "candidates_studyB_20251231_174014.json"
    
    # 出力ファイル
    output_file = "holdout_results_with_holdings.json"
    
    # コマンドを構築
    cmd = [
        "python",
        "evaluate_candidates_holdout.py",
        "--candidates", candidates_file,
        "--holdout-start", "2023-01-01",
        "--holdout-end", "2024-12-31",
        "--cost-bps", "0.0",
        "--output", output_file,
        "--use-cache",
    ]
    
    print("Holdout評価を実行します（ポートフォリオ情報を含む）...")
    print(f"コマンド: {' '.join(cmd)}")
    print()
    
    # 実行
    result = subprocess.run(cmd, check=False)
    
    if result.returncode == 0:
        print("\n✅ Holdout評価が完了しました！")
        print(f"結果ファイル: {output_file}")
        print("\n次のコマンドで可視化を実行できます:")
        print("  python visualize_holdings_details.py")
    else:
        print(f"\n❌ エラーが発生しました（終了コード: {result.returncode}）")
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()











