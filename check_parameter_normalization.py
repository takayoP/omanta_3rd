"""
パラメータ正規化の確認スクリプト

最適化結果JSONファイルのパラメータが正規化されているか確認します。
"""

import json
import sys
from pathlib import Path


def check_normalization(json_file: str):
    """
    最適化結果JSONファイルのパラメータ正規化を確認
    
    Args:
        json_file: 最適化結果JSONファイルのパス
    """
    print(f"最適化結果ファイルを読み込み中: {json_file}")
    
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    best_params = data.get("best_params", {})
    n_trials = data.get("n_trials", "不明")
    
    print(f"\n試行回数: {n_trials}")
    print(f"最良目的関数値: {data.get('best_value', '不明')}")
    print()
    
    # Core Score重みの合計を確認
    w_quality = best_params.get("w_quality", 0.0)
    w_value = best_params.get("w_value", 0.0)
    w_growth = best_params.get("w_growth", 0.0)
    w_record_high = best_params.get("w_record_high", 0.0)
    w_size = best_params.get("w_size", 0.0)
    
    total = w_quality + w_value + w_growth + w_record_high + w_size
    
    print("=" * 80)
    print("Core Score重みの確認")
    print("=" * 80)
    print(f"w_quality:      {w_quality:.6f} ({w_quality*100:.2f}%)")
    print(f"w_value:        {w_value:.6f} ({w_value*100:.2f}%)")
    print(f"w_growth:       {w_growth:.6f} ({w_growth*100:.2f}%)")
    print(f"w_record_high:  {w_record_high:.6f} ({w_record_high*100:.2f}%)")
    print(f"w_size:         {w_size:.6f} ({w_size*100:.2f}%)")
    print(f"合計:           {total:.6f}")
    print()
    
    if abs(total - 1.0) < 0.0001:
        print("✅ 正規化されています（合計 ≈ 1.0）")
        print("   → JSONの値は「実効比率」として解釈できます")
    else:
        print("⚠️  正規化されていません（合計 ≠ 1.0）")
        print("   → 実装を確認する必要があります")
        print()
        print("   実装上の問題の可能性:")
        print("   1. 正規化処理が実行されていない")
        print("   2. JSON保存時に正規化前の値が保存されている")
        print("   3. 正規化処理にバグがある")
    
    # Value Score重みの確認
    w_forward_per = best_params.get("w_forward_per", 0.0)
    w_pbr = 1.0 - w_forward_per  # 実装では自動計算
    
    print()
    print("=" * 80)
    print("Value Score重みの確認")
    print("=" * 80)
    print(f"w_forward_per:  {w_forward_per:.6f} ({w_forward_per*100:.2f}%)")
    print(f"w_pbr:          {w_pbr:.6f} ({w_pbr*100:.2f}%)")
    print(f"合計:           {w_forward_per + w_pbr:.6f}")
    print()
    
    if abs((w_forward_per + w_pbr) - 1.0) < 0.0001:
        print("✅ Value Score重みは正規化されています")
    else:
        print("⚠️  Value Score重みが正規化されていません")
    
    # Entry Score重みの確認
    bb_weight = best_params.get("bb_weight", 0.0)
    rsi_weight = 1.0 - bb_weight  # 実装では自動計算
    
    print()
    print("=" * 80)
    print("Entry Score重みの確認")
    print("=" * 80)
    print(f"bb_weight:      {bb_weight:.6f} ({bb_weight*100:.2f}%)")
    print(f"rsi_weight:     {rsi_weight:.6f} ({rsi_weight*100:.2f}%)")
    print(f"合計:           {bb_weight + rsi_weight:.6f}")
    print()
    
    if abs((bb_weight + rsi_weight) - 1.0) < 0.0001:
        print("✅ Entry Score重みは正規化されています")
    else:
        print("⚠️  Entry Score重みが正規化されていません")
    
    # 境界張り付きパラメータの確認
    print()
    print("=" * 80)
    print("境界張り付きパラメータの確認")
    print("=" * 80)
    
    # 探索範囲（第2回最適化の範囲を想定）
    ranges = {
        "w_quality": (0.15, 0.35),
        "w_value": (0.20, 0.40),
        "w_growth": (0.05, 0.20),
        "w_record_high": (0.03, 0.15),
        "w_size": (0.10, 0.25),
        "w_forward_per": (0.35, 0.65),
        "roe_min": (0.05, 0.12),
        "liquidity_quantile_cut": (0.15, 0.35),
        "rsi_base": (35.0, 60.0),
        "rsi_max": (70.0, 85.0),
        "bb_z_base": (-2.0, 0.0),
        "bb_z_max": (2.0, 3.5),
        "bb_weight": (0.45, 0.75),
    }
    
    boundary_threshold = 0.05  # 境界から5%以内を「張り付き」と判定
    
    for param_name, (min_val, max_val) in ranges.items():
        if param_name not in best_params:
            continue
        
        value = best_params[param_name]
        range_size = max_val - min_val
        distance_from_min = (value - min_val) / range_size if range_size > 0 else 0.0
        distance_from_max = (max_val - value) / range_size if range_size > 0 else 0.0
        
        is_near_min = distance_from_min < boundary_threshold
        is_near_max = distance_from_max < boundary_threshold
        
        if is_near_min:
            print(f"⚠️  {param_name}: {value:.6f} (下限近傍: {min_val:.6f}から{distance_from_min*100:.1f}%)")
        elif is_near_max:
            print(f"⚠️  {param_name}: {value:.6f} (上限近傍: {max_val:.6f}から{distance_from_max*100:.1f}%)")
        else:
            print(f"✅ {param_name}: {value:.6f} (範囲内)")
    
    print()
    print("=" * 80)
    print("まとめ")
    print("=" * 80)
    
    if abs(total - 1.0) < 0.0001:
        print("✅ Core Score重みは正規化されています")
        print("   → JSONの値は「実効比率」として解釈できます")
        print("   → 実装上の問題はありません")
    else:
        print("❌ Core Score重みが正規化されていません")
        print("   → 実装を確認する必要があります")
        print("   → src/omanta_3rd/jobs/optimize.py の正規化処理を確認してください")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python check_parameter_normalization.py <最適化結果JSONファイル>")
        print()
        print("例:")
        print("  python check_parameter_normalization.py optimization_result_optimization_20251229_212329.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    
    if not Path(json_file).exists():
        print(f"❌ ファイルが見つかりません: {json_file}")
        sys.exit(1)
    
    check_normalization(json_file)







