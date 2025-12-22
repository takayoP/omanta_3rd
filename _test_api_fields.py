"""J-Quants APIのフィールドを確認"""
from omanta_3rd.infra.jquants import JQuantsClient
from datetime import datetime, timedelta

client = JQuantsClient()

# 最新の日付でサンプルデータを取得
date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
print(f"日付: {date}")

try:
    rows = client.get_all_pages("/prices/daily_quotes", params={"date": date, "code": "7419"})
    if rows:
        print("\n利用可能なフィールド:")
        sample = rows[0]
        for key in sorted(sample.keys()):
            value = sample[key]
            if isinstance(value, (int, float)):
                print(f"  {key}: {value}")
            else:
                print(f"  {key}: {str(value)[:50]}")
        
        # CloseとAdjustmentCloseの両方があるか確認
        if "Close" in sample:
            print(f"\nClose（調整前終値）: {sample.get('Close')}")
        if "AdjustmentClose" in sample:
            print(f"AdjustmentClose（調整後終値）: {sample.get('AdjustmentClose')}")
except Exception as e:
    print(f"エラー: {e}")
