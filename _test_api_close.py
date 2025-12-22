"""
J-Quants APIからCloseフィールドが取得できるかテスト
"""

from src.omanta_3rd.infra.jquants import JQuantsClient
import json

# テスト用の日付と銘柄コード
test_date = "2025-12-19"
test_code = "7419"

print(f"J-Quants APIからCloseフィールドを取得するテスト")
print(f"日付: {test_date}, 銘柄コード: {test_code}")
print("=" * 80)

try:
    client = JQuantsClient()
    
    # APIからデータを取得
    print("\n【APIレスポンスの確認】")
    rows = client.get_all_pages("/prices/daily_quotes", params={"date": test_date})
    
    if not rows:
        print("データが取得できませんでした")
    else:
        # テスト銘柄のデータを探す
        test_row = None
        for row in rows:
            if str(row.get("Code", "")).strip() == test_code:
                test_row = row
                break
        
        if test_row:
            print(f"\n【取得できたフィールド】")
            print(f"全フィールド: {list(test_row.keys())}")
            print(f"\n【価格関連フィールド】")
            for key in ["Close", "close", "AdjustmentClose", "AdjustmentClose", "AdjustmentFactor"]:
                if key in test_row:
                    print(f"  {key}: {test_row[key]}")
                else:
                    # 大文字小文字を無視して検索
                    found = False
                    for k in test_row.keys():
                        if k.lower() == key.lower():
                            print(f"  {k} (大文字小文字が異なる): {test_row[k]}")
                            found = True
                            break
                    if not found:
                        print(f"  {key}: 見つかりません")
            
            print(f"\n【サンプルデータ（JSON）】")
            print(json.dumps(test_row, indent=2, ensure_ascii=False))
        else:
            print(f"\n銘柄コード {test_code} のデータが見つかりません")
            if len(rows) > 0:
                print(f"\n【最初のレコードのフィールド（参考）】")
                sample = rows[0]
                print(f"全フィールド: {list(sample.keys())}")
                print(f"\n【サンプルデータ（JSON）】")
                print(json.dumps(sample, indent=2, ensure_ascii=False))

except Exception as e:
    print(f"\nエラーが発生しました: {e}")
    import traceback
    traceback.print_exc()
