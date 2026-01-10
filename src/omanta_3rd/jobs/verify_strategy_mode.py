"""
既存のパラメータファイルの戦略モードを再判定するスクリプト
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Literal

from ..config.settings import PROJECT_ROOT
from .reoptimize_all_candidates import determine_strategy_mode


def verify_strategy_mode(params_file: Path) -> None:
    """
    パラメータファイルの戦略モードを再判定
    
    Args:
        params_file: パラメータファイルのパス
    """
    with open(params_file, "r", encoding="utf-8") as f:
        params_data = json.load(f)
    
    params = params_data["params"]
    current_mode = params_data["metadata"].get("strategy_mode", "不明")
    
    # 再判定
    best_params = {
        "rsi_base": params["rsi_base"],
        "rsi_max": params["rsi_max"],
        "bb_z_base": params["bb_z_base"],
        "bb_z_max": params["bb_z_max"],
        "bb_weight": params["bb_weight"],
    }
    
    new_mode = determine_strategy_mode(best_params)
    
    print(f"ファイル: {params_file.name}")
    print(f"  現在の戦略モード: {current_mode}")
    print(f"  再判定結果: {new_mode}")
    print(f"  パラメータ:")
    print(f"    RSI: base={params['rsi_base']:.2f}, max={params['rsi_max']:.2f} ({'順張り' if params['rsi_max'] > params['rsi_base'] else '逆張り'})")
    print(f"    BB: base={params['bb_z_base']:.2f}, max={params['bb_z_max']:.2f} ({'順張り' if params['bb_z_max'] > params['bb_z_base'] else '逆張り'})")
    print(f"    重み: RSI={1.0 - params['bb_weight']:.2f}, BB={params['bb_weight']:.2f}")
    
    if current_mode != new_mode:
        print(f"  ⚠️  戦略モードが不一致です！")
    else:
        print(f"  ✓ 戦略モードは一致しています")
    print()


def main():
    """すべてのパラメータファイルを検証"""
    print("=" * 80)
    print("戦略モードの再判定")
    print("=" * 80)
    print()
    
    # 最新のパラメータファイルを検索
    param_files = [
        PROJECT_ROOT / "params_operational_24M_20260109.json",
        PROJECT_ROOT / "params_12M_momentum_20260109.json",
        PROJECT_ROOT / "params_12M_reversal_20260109.json",
    ]
    
    for params_file in param_files:
        if params_file.exists():
            verify_strategy_mode(params_file)
        else:
            print(f"ファイルが見つかりません: {params_file.name}")
            print()


if __name__ == "__main__":
    main()

