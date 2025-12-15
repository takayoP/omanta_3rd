import sqlite3
c=sqlite3.connect(r"data/db/jquants.sqlite")
rows=c.execute("select market_name, count(*) from listed_info where date='2025-12-12' group by market_name order by count(*) desc").fetchall()
print(rows)
c.close()
