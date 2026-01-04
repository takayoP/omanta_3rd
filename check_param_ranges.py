"""現在のパラメータ範囲を確認"""

print("=" * 80)
print("Study B のパラメータ範囲")
print("=" * 80)
print()

# Study B のパラメータ範囲
ranges = {
    "w_quality": (0.15, 0.35, 0.20),
    "w_growth": (0.05, 0.20, 0.15),
    "w_record_high": (0.035, 0.065, 0.03),
    "w_size": (0.10, 0.25, 0.15),
    "w_value": (0.33, 0.50, 0.17),
    "w_forward_per": (0.30, 0.55, 0.25),
    "roe_min": (0.08, 0.15, 0.07),
    "bb_weight": (0.40, 0.65, 0.25),
    "liquidity_quantile_cut": (0.16, 0.25, 0.09),
    "rsi_base": (40.0, 58.0, 18.0),
    "rsi_max": (76.5, 79.0, 2.5),
    "bb_z_base": (-2.0, -0.8, 1.2),
    "bb_z_max": (2.0, 3.6, 1.6),
}

print("パラメータ名 | 最小値 | 最大値 | 範囲幅 | 評価")
print("-" * 80)

for name, (min_val, max_val, width) in ranges.items():
    # 範囲の広さを評価
    if width < 0.1:
        evaluation = "狭い"
    elif width < 0.2:
        evaluation = "中程度"
    else:
        evaluation = "広い"
    
    print(f"{name:20s} | {min_val:6.2f} | {max_val:6.2f} | {width:6.2f} | {evaluation}")

print()
print("=" * 80)
print("注意事項")
print("=" * 80)
print("1. w_quality, w_growth, w_record_high, w_size, w_value は正規化されるため、")
print("   実際の探索空間は制約されます（合計が1になるように調整）。")
print()
print("2. w_forward_per と w_pbr は w_pbr = 1.0 - w_forward_per の関係があります。")
print()
print("3. bb_weight と rsi_weight は rsi_weight = 1.0 - bb_weight の関係があります。")
print()
print("4. 実際の探索空間のサイズは、これらの制約により大幅に縮小されます。")



