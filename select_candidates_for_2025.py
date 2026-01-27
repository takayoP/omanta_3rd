"""指定されたtrial_numberの候補を抽出するスクリプト"""

import json
from pathlib import Path

# 入力ファイル
input_file = "candidates_studyB_20251231_174014.json"
output_file = "candidates_selected_2025_live.json"

# 選択するtrial_number
selected_trial_numbers = [196, 180, 96, 168]

# 候補を読み込み
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

candidates = data.get("candidates", [])

# 指定されたtrial_numberの候補を抽出
selected = [c for c in candidates if c.get("trial_number") in selected_trial_numbers]

print(f"選択された候補数: {len(selected)}/{len(candidates)}")
print()

for c in selected:
    trial_num = c.get("trial_number")
    sharpe = c.get("value", 0)
    print(f"  Trial #{trial_num}: Sharpe={sharpe:.4f}")

print()

# 結果を保存
result = {
    "candidates": selected,
    "metadata": {
        "source_file": input_file,
        "selected_trial_numbers": selected_trial_numbers,
        "selection_reason": "コスト耐性で残る組（#196, #180, #96, #168）",
        "target_period": "2025疑似ライブ",
        "cost_bps": 10.0,
    }
}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"候補ファイルを作成しました: {output_file}")


















