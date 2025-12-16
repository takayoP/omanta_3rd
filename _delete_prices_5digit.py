import sqlite3
c=sqlite3.connect(r"data/db/jquants.sqlite")
n = c.execute("select count(*) from prices_daily where length(code)=5").fetchone()[0]
c.execute("delete from prices_daily where length(code)=5")
c.commit()
c.close()
print("deleted 5-digit rows:", n)
