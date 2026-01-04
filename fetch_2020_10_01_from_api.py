"""J-Quants APIから2020-10-01のデータを取得して確認"""

from src.omanta_3rd.infra.jquants import JQuantsClient
from src.omanta_3rd.ingest.prices import fetch_prices_by_date, _map_price_row
import json

print("=" * 80)
print("J-Quants APIから2020-10-01のデータを取得")
print("=" * 80)

client = JQuantsClient()

try:
    # APIからデータを取得
    print("\nAPIからデータを取得中...")
    rows = fetch_prices_by_date(client, "2020-10-01")
    
    print(f"取得したレコード数: {len(rows)}")
    
    if rows:
        # 最初の10件を確認
        print("\n最初の10件の生データ（APIレスポンス）:")
        for i, row in enumerate(rows[:10], 1):
            print(f"\n{i}. Code: {row.get('Code')}, Date: {row.get('Date')}")
            print(f"   O (始値): {row.get('O')}")
            print(f"   C (終値): {row.get('C')}")
            print(f"   AdjC (調整済終値): {row.get('AdjC')}")
            print(f"   AdjFactor: {row.get('AdjFactor')}")
            print(f"   AdjVo: {row.get('AdjVo')}")
            print(f"   Va: {row.get('Va')}")
        
        # マッピング後のデータを確認
        print("\n" + "=" * 80)
        print("マッピング後のデータ（最初の10件）:")
        print("=" * 80)
        mapped = [_map_price_row(r) for r in rows[:10]]
        for i, m in enumerate(mapped, 1):
            print(f"\n{i}. {m}")
        
        # 統計情報
        print("\n" + "=" * 80)
        print("統計情報")
        print("=" * 80)
        
        # O（始値）がNULLでない件数
        o_not_null = sum(1 for r in rows if r.get("O") is not None)
        print(f"O（始値）がNULLでない件数: {o_not_null}/{len(rows)}")
        
        # C（終値）がNULLでない件数
        c_not_null = sum(1 for r in rows if r.get("C") is not None)
        print(f"C（終値）がNULLでない件数: {c_not_null}/{len(rows)}")
        
        # AdjC（調整済終値）がNULLでない件数
        adjc_not_null = sum(1 for r in rows if r.get("AdjC") is not None)
        print(f"AdjC（調整済終値）がNULLでない件数: {adjc_not_null}/{len(rows)}")
        
        # すべてがNULLの件数
        all_null = sum(1 for r in rows if r.get("O") is None and r.get("C") is None and r.get("AdjC") is None)
        print(f"すべての価格がNULLの件数: {all_null}/{len(rows)}")
        
        # サンプル: 価格データがある銘柄の例
        print("\n価格データがある銘柄の例（最初の5件）:")
        count = 0
        for r in rows:
            if r.get("O") is not None or r.get("C") is not None or r.get("AdjC") is not None:
                print(f"  Code: {r.get('Code')}, O: {r.get('O')}, C: {r.get('C')}, AdjC: {r.get('AdjC')}")
                count += 1
                if count >= 5:
                    break
        
    else:
        print("データが取得できませんでした（空のレスポンス）")
        
except Exception as e:
    print(f"エラーが発生しました: {e}")
    import traceback
    traceback.print_exc()



