import sqlite3
c=sqlite3.connect(r"data/db/jquants.sqlite")
rows = c.execute("""
select code, core_score, entry_score
from portfolio_monthly
where rebalance_date='2025-12-12'
order by core_score desc
limit 30
""").fetchall()
print("top30 count:", len(rows))
c.close()
