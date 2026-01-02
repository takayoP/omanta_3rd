"""スキーマファイルの更新を確認"""

from pathlib import Path

schema_file = Path('sql/schema.sql')
schema_content = schema_file.read_text(encoding='utf-8')

print(f"schema.sql の行数: {len(schema_content.splitlines())}")

# 新しいテーブル定義が含まれているか確認
if 'monthly_rebalance_final_selected_candidates' in schema_content:
    print("✓ monthly_rebalance_final_selected_candidates テーブル定義が含まれています")
else:
    print("✗ monthly_rebalance_final_selected_candidates テーブル定義が見つかりません")

if 'monthly_rebalance_candidate_performance' in schema_content:
    print("✓ monthly_rebalance_candidate_performance テーブル定義が含まれています")
else:
    print("✗ monthly_rebalance_candidate_performance テーブル定義が見つかりません")

if 'monthly_rebalance_candidate_monthly_returns' in schema_content:
    print("✓ monthly_rebalance_candidate_monthly_returns テーブル定義が含まれています")
else:
    print("✗ monthly_rebalance_candidate_monthly_returns テーブル定義が見つかりません")

if 'monthly_rebalance_candidate_detailed_metrics' in schema_content:
    print("✓ monthly_rebalance_candidate_detailed_metrics テーブル定義が含まれています")
else:
    print("✗ monthly_rebalance_candidate_detailed_metrics テーブル定義が見つかりません")

# テーブル番号を確認
import re
table_numbers = re.findall(r'-- (\d+)\)', schema_content)
print(f"\n定義されているテーブル数: {len(table_numbers)}")
print(f"最後のテーブル番号: {table_numbers[-1] if table_numbers else 'N/A'}")

