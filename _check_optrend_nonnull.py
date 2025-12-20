import sqlite3
c=sqlite3.connect(r"data/db/jquants.sqlite")
n = c.execute("select count(*) from features_monthly where as_of_date='2025-12-12' and op_trend is not null").fetchone()[0]
m = c.execute("select count(*) from features_monthly where as_of_date='2025-12-12'").fetchone()[0]
print("op_trend not null:", n, "/", m)
c.close()
