"""DBのテーブル・行数を確認"""
from omanta_3rd.infra.db import connect_db

with connect_db(read_only=True) as c:
    r = c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    tables = [x[0] for x in r]
    print("Tables:", len(tables))
    for t in ["prices_daily", "fins_statements", "listed_info", "index_daily"]:
        if t in tables:
            n = c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            print(f"  {t}: {n} rows")
        else:
            print(f"  {t}: (no table)")
