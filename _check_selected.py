import sqlite3
c = sqlite3.connect(r"data/db/jquants.sqlite")
asof = "2025-12-12"
n = c.execute("select count(*) from portfolio_monthly where rebalance_date=?", (asof,)).fetchone()[0]
print("selected:", n)
c.close()
