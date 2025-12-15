import sqlite3
c = sqlite3.connect(r"data/db/jquants.sqlite")
rows = c.execute("select substr(disclosed_date,1,10), count(*) from fins_statements group by substr(disclosed_date,1,10) order by count(*) desc limit 5").fetchall()
print("top disclosed_date samples:", rows)
lens = c.execute("select length(disclosed_date), count(*) from fins_statements group by length(disclosed_date) order by length(disclosed_date)").fetchall()
print("length distribution:", lens)
c.close()
