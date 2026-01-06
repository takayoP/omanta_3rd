"""2020-09-30のリバランス日の翌営業日を確認"""

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.backtest.performance import _get_next_trading_day
from datetime import datetime

rebalance_date = "2020-09-30"

print("=" * 80)
print(f"リバランス日: {rebalance_date}")
print("=" * 80)

# リバランス日の曜日を確認
rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
weekday_names = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
print(f"リバランス日の曜日: {weekday_names[rebalance_dt.weekday()]}")

with connect_db() as conn:
    # 翌営業日を取得
    next_trading_day = _get_next_trading_day(conn, rebalance_date)
    
    if next_trading_day:
        print(f"\n取得された翌営業日: {next_trading_day}")
        
        # 翌営業日の曜日を確認
        next_dt = datetime.strptime(next_trading_day, "%Y-%m-%d")
        print(f"翌営業日の曜日: {weekday_names[next_dt.weekday()]}")
        
        # 日数差を計算
        days_diff = (next_dt - rebalance_dt).days
        print(f"日数差: {days_diff}日")
        
        # 2020-10-01のデータを確認
        import pandas as pd
        oct_01_count = pd.read_sql_query(
            "SELECT COUNT(DISTINCT code) as count FROM prices_daily WHERE date = ? AND (open IS NOT NULL OR close IS NOT NULL)",
            conn,
            params=("2020-10-01",),
        )
        print(f"\n2020-10-01に価格データがある銘柄数: {oct_01_count['count'].iloc[0] if not oct_01_count.empty else 0}")
        
        # 2020-10-02のデータを確認
        oct_02_count = pd.read_sql_query(
            "SELECT COUNT(DISTINCT code) as count FROM prices_daily WHERE date = ? AND (open IS NOT NULL OR close IS NOT NULL)",
            conn,
            params=("2020-10-02",),
        )
        print(f"2020-10-02に価格データがある銘柄数: {oct_02_count['count'].iloc[0] if not oct_02_count.empty else 0}")
        
        print("\n" + "=" * 80)
        print("結論")
        print("=" * 80)
        if next_trading_day == "2020-10-02":
            print("✅ リバランス日2020-09-30の場合、買い付けは2020-10-02（金曜日）に行われます。")
            print("   これは、2020-10-01（木曜日）がシステム障害で取引がなかったため、")
            print("   実際に取引が可能な最初の営業日である2020-10-02が正しく選択されています。")
        else:
            print(f"⚠️  予期しない結果: 翌営業日が{next_trading_day}になっています。")
    else:
        print("\n❌ 翌営業日が見つかりませんでした。")











