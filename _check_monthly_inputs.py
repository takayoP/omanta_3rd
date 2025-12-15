import sqlite3
c = sqlite3.connect(r"data/db/jquants.sqlite")

def show(asof):
    px = c.execute("select count(*) from prices_daily where date=?", (asof,)).fetchone()[0]
    li = c.execute("select count(*) from listed_info where date=?", (asof,)).fetchone()[0]
    print("asof", asof, "| prices rows:", px, "| listed rows:", li)

print("prices max:", c.execute("select max(date) from prices_daily").fetchone()[0])
print("listed max:", c.execute("select max(date) from listed_info").fetchone()[0])
show("2025-12-12")
show("2025-12-15")
c.close()
