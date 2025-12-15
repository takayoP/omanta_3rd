import sqlite3
c = sqlite3.connect(r"data/db/jquants.sqlite")
print("fins rows:", c.execute("select count(*) from fins_statements").fetchone()[0])
print("FY rows:", c.execute("select count(*) from fins_statements where type_of_current_period='FY'").fetchone()[0])
c.close()
