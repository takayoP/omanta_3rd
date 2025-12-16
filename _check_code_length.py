import sqlite3
c=sqlite3.connect(r"data/db/jquants.sqlite")
print("prices code length:", c.execute("select length(code), count(*) from prices_daily group by length(code) order by length(code)").fetchall())
print("listed code length:", c.execute("select length(code), count(*) from listed_info where date='2025-12-12' group by length(code)").fetchall())
print("fins code length:", c.execute("select length(code), count(*) from fins_statements group by length(code) order by length(code)").fetchall())
c.close()
