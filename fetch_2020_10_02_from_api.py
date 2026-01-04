"""J-Quants APIから2020-10-02のデータを取得して確認"""

from src.omanta_3rd.infra.jquants import JQuantsClient
from src.omanta_3rd.ingest.prices import fetch_prices_by_date, _map_price_row

print("=" * 80)
print("J-Quants APIから2020-10-02のデータを取得")
print("=" * 80)

client = JQuantsClient()

try:
    # APIからデータを取得
    print("\nAPIからデータを取得中...")
    rows = fetch_prices_by_date(client, "2020-10-02")
    
    print(f"取得したレコード数: {len(rows)}")
    
    if rows:
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



