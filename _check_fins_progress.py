import sqlite3
c = sqlite3.connect(r"data/db/jquants.sqlite")
rows = c.execute("select code, count(*) cnt from fins_statements group by code order by cnt desc limit 10").fetchall()
print("top codes:", rows)
print("distinct codes:", c.execute("select count(distinct code) from fins_statements").fetchone()[0])
c.close()
