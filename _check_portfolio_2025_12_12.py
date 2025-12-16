import sqlite3
c=sqlite3.connect(r"data/db/jquants.sqlite")
rows=c.execute("select code, weight, core_score, entry_score from portfolio_monthly where rebalance_date='2025-12-12' order by core_score desc limit 30").fetchall()
print("top 30:", rows[:10])
print("count:", c.execute("select count(*) from portfolio_monthly where rebalance_date='2025-12-12'").fetchone()[0])
c.close()
