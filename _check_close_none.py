"""
closeがNoneになっているレコードの原因を調査
"""

from src.omanta_3rd.infra.jquants import JQuantsClient
from src.omanta_3rd.ingest.prices import _map_price_row
import json

# テスト用の日付
test_date = "2019-01-04"

print(f"closeがNoneになっているレコードの原因を調査")
print(f"日付: {test_date}")
print("=" * 80)

try:
    client = JQuantsClient()
    
    # APIからデータを取得
    rows = client.get_all_pages("/prices/daily_quotes", params={"date": test_date})
    
    if not rows:
        print("データが取得できませんでした")
    else:
        print(f"\n取得したレコード数: {len(rows)}")
        
        # closeがNoneになるレコードを探す
        none_close_records = []
        for row in rows:
            mapped = _map_price_row(row)
            if mapped.get("close") is None:
                none_close_records.append({
                    "original": row,
                    "mapped": mapped
                })
        
        print(f"\ncloseがNoneのレコード数: {len(none_close_records)}")
        
        if none_close_records:
            print(f"\n【サンプル（最初の5件）】")
            for i, rec in enumerate(none_close_records[:5], 1):
                print(f"\n--- サンプル {i} ---")
                print(f"Code: {rec['original'].get('Code')}")
                print(f"Date: {rec['original'].get('Date')}")
                print(f"Close (API): {rec['original'].get('Close')}")
                print(f"AdjustmentClose (API): {rec['original'].get('AdjustmentClose')}")
                print(f"全フィールド: {list(rec['original'].keys())}")
                print(f"マッピング後: {rec['mapped']}")
            
            # 統計情報
            print(f"\n【統計情報】")
            codes_with_none = [rec['original'].get('Code') for rec in none_close_records]
            print(f"closeがNoneの銘柄コード（ユニーク）: {len(set(codes_with_none))}件")
            print(f"サンプル銘柄コード: {list(set(codes_with_none))[:10]}")
            
            # Closeフィールドが存在するか確認
            has_close = sum(1 for rec in none_close_records if 'Close' in rec['original'])
            has_adj_close = sum(1 for rec in none_close_records if 'AdjustmentClose' in rec['original'])
            print(f"\nCloseフィールドが存在する: {has_close}/{len(none_close_records)}")
            print(f"AdjustmentCloseフィールドが存在する: {has_adj_close}/{len(none_close_records)}")
            
            # CloseがNoneでAdjustmentCloseが存在するケース
            close_none_adj_exists = [
                rec for rec in none_close_records
                if rec['original'].get('Close') is None and rec['original'].get('AdjustmentClose') is not None
            ]
            print(f"\nCloseがNoneでAdjustmentCloseが存在する: {len(close_none_adj_exists)}件")
            if close_none_adj_exists:
                print("【このケースのサンプル】")
                sample = close_none_adj_exists[0]
                print(f"Code: {sample['original'].get('Code')}")
                print(f"Close: {sample['original'].get('Close')}")
                print(f"AdjustmentClose: {sample['original'].get('AdjustmentClose')}")
                print(f"マッピング後close: {sample['mapped'].get('close')}")
        else:
            print("\ncloseがNoneのレコードはありませんでした")

except Exception as e:
    print(f"\nエラーが発生しました: {e}")
    import traceback
    traceback.print_exc()
