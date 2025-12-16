import sqlite3
db = r"data/db/jquants.sqlite"
c = sqlite3.connect(db)

cols = [r[1] for r in c.execute("PRAGMA table_info(features_monthly)").fetchall()]
need = ["op_trend"]
for col in need:
    if col not in cols:
        c.execute(f"ALTER TABLE features_monthly ADD COLUMN {col} REAL")
        print("added column:", col)
    else:
        print("already exists:", col)

c.commit()
c.close()
print("done")
