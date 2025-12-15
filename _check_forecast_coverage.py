import sqlite3
c = sqlite3.connect(r"data/db/jquants.sqlite")
print("forecast_eps not null:", c.execute("select count(*) from fins_statements where forecast_eps is not null").fetchone()[0])
print("forecast_op not null:", c.execute("select count(*) from fins_statements where forecast_operating_profit is not null").fetchone()[0])
print("forecast rows FY:", c.execute("select count(*) from fins_statements where type_of_current_period='FY' and forecast_eps is not null").fetchone()[0])
c.close()
