import sqlite3
c=sqlite3.connect(r"data/db/jquants.sqlite")
rows=c.execute("select code, count(*) cnt from prices_daily where length(code)=5 group by code order by cnt desc limit 20").fetchall()
print("top 5-digit codes:", rows)
print("distinct 5-digit codes:", c.execute("select count(distinct code) from prices_daily where length(code)=5").fetchone()[0])
c.close()
