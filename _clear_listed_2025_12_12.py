import sqlite3
c=sqlite3.connect(r"data/db/jquants.sqlite")
c.execute("delete from listed_info where date=?", ("2025-12-12",))
c.commit()
c.close()
print("cleared listed_info for 2025-12-12")
