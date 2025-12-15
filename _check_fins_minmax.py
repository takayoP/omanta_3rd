import sqlite3
c = sqlite3.connect(r"data/db/jquants.sqlite")
print("min disclosed_date:", c.execute("select min(disclosed_date) from fins_statements").fetchone()[0])
print("max disclosed_date:", c.execute("select max(disclosed_date) from fins_statements").fetchone()[0])
c.close()
