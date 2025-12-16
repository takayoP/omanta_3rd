import sqlite3
c=sqlite3.connect(r"data/db/jquants.sqlite")

rows = c.execute("""
select p.code,
       p.core_score,
       f.op_trend,
       f.op_growth,
       f.profit_growth,
       f.roe,
       f.forward_per
from portfolio_monthly p
join features_monthly f
  on p.rebalance_date = f.as_of_date and p.code = f.code
where p.rebalance_date='2025-12-12'
order by p.core_score desc
limit 30
""").fetchall()

print("rows:", len(rows))
print("top10:")
for r in rows[:10]:
    print(r)

# op_trend の簡単統計
op = [r[2] for r in rows if r[2] is not None]
print("op_trend not-null:", len(op), "/", len(rows))
if op:
    print("op_trend min/median/max:", min(op), sorted(op)[len(op)//2], max(op))

c.close()
