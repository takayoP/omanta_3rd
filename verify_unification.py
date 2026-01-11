"""
統一確認スクリプト：compare側とoptimize側で同じparamsファイルを使用して
portfolio_hashが一致することを確認

このスクリプトは、compare側とoptimize側の両方のデバッグ出力をキャプチャして
比較します。デバッグ出力は標準出力にJSON形式で出力されるため、
サブプロセスで実行してキャプチャします。

使用方法:
    python verify_unification.py --params-file params_operational_24M_lambda0.00_best_20260111_154617.json --rebalance-date 2023-01-31
    
    # 複数の日付をチェック
    python verify_unification.py --params-file params_operational_24M_lambda0.00_best_20260111_154617.json --rebalance-dates 2023-01-31 2023-02-28 2023-03-31
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from omanta_3rd.config.settings import PROJECT_ROOT


def extract_debug_json(output: str, prefix: str) -> Optional[Dict[str, Any]]:
    """デバッグ出力からJSONを抽出"""
    # パターン: [PREFIX] {json}
    pattern = rf"\[{re.escape(prefix)}\]\s+({{.*}})"
    match = re.search(pattern, output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def run_compare_route(
    params_file: str,
    rebalance_date: str,
    as_of_date: str,
    horizon_months: int,
) -> Dict[str, Any]:
    """compare側を実行してデバッグ出力を取得"""
    # compare側はrun_backtest_with_params_fileを使用
    # 実際には、compare_lambda_penalties.pyの関数を直接呼ぶか、
    # 別のスクリプトを作成する必要がある
    
    # ここでは簡易的に、実際の実行は別のスクリプトで行うことを想定
    # または、compare_lambda_penalties.pyを修正してデバッグ情報を返すようにする
    
    # 現在は、標準出力にJSONが出力されることを前提とする
    pass


def run_optimize_route(
    params_file: str,
    rebalance_date: str,
    as_of_date: str,
    horizon_months: int,
) -> Dict[str, Any]:
    """optimize側を実行してデバッグ出力を取得"""
    # optimize側はcalculate_longterm_performanceを使用
    # 実際には、optimize_longterm.pyの関数を直接呼ぶ
    
    # 現在は、標準出力にJSONが出力されることを前提とする
    pass


def main():
    parser = argparse.ArgumentParser(description="統一確認スクリプト")
    parser.add_argument(
        "--params-file",
        type=str,
        required=True,
        help="パラメータファイル名",
    )
    parser.add_argument(
        "--rebalance-date",
        type=str,
        help="リバランス日（単一）",
    )
    parser.add_argument(
        "--rebalance-dates",
        type=str,
        nargs="+",
        help="リバランス日（複数）",
    )
    parser.add_argument(
        "--as-of-date",
        type=str,
        default="2025-12-31",
        help="評価の打ち切り日",
    )
    parser.add_argument(
        "--horizon-months",
        type=int,
        default=24,
        help="投資ホライズン（月数）",
    )
    
    args = parser.parse_args()
    
    if args.rebalance_date:
        rebalance_dates = [args.rebalance_date]
    elif args.rebalance_dates:
        rebalance_dates = args.rebalance_dates
    else:
        parser.error("--rebalance-date または --rebalance-dates を指定してください")
    
    print(f"統一確認: {args.params_file}")
    print(f"rebalance_dates: {rebalance_dates}")
    print(f"horizon_months: {args.horizon_months}")
    print(f"as_of_date: {args.as_of_date}")
    print()
    
    # 実際の実行は、compare_lambda_penalties.pyとoptimize_longterm.pyを
    # 直接呼び出すか、別の方法で実装する必要がある
    print("このスクリプトは実装中です。")
    print("現在は、以下の方法で確認してください：")
    print()
    print("1. compare側: compare_lambda_penalties.pyを実行してDEBUG_COMPARE出力を確認")
    print("2. optimize側: optimize_longterm.pyを実行してDEBUG出力を確認")
    print("3. 両方のJSON出力を比較して、portfolio_hashが一致することを確認")


if __name__ == "__main__":
    main()

