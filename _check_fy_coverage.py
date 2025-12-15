import sqlite3
c = sqlite3.connect(r"data/db/jquants.sqlite")
print("distinct codes (all):", c.execute("select count(distinct code) from fins_statements").fetchone()[0])
print("distinct codes (FY):", c.execute("select count(distinct code) from fins_statements where type_of_current_period='FY'").fetchone()[0])
c.close()
