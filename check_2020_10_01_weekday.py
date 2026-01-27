"""2020-10-01の曜日を確認"""

from datetime import datetime

d = datetime(2020, 10, 1)
weekday_names = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
print(f"2020-10-01は{weekday_names[d.weekday()]}です（weekday={d.weekday()}）")

# 2020-10-03も確認
d2 = datetime(2020, 10, 3)
print(f"2020-10-03は{weekday_names[d2.weekday()]}です（weekday={d2.weekday()}）")















