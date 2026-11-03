import sqlite3
import sys

db = sqlite3.connect(sys.argv[1] if len(sys.argv) > 1 else "runtime/steedatlas.db")
print("tables:", sorted(r[0] for r in db.execute("select name from sqlite_master where type='table'")))
for table in ("users", "v2_entities", "v2_jobs", "v2_nodes"):
    try:
        cols = [d[0] for d in db.execute(f"select * from {table} limit 1").description]
        print(table, cols, "count=", db.execute(f"select count(*) from {table}").fetchone()[0])
        for row in list(db.execute(f"select * from {table} limit 3")):
            print("   ", row)
    except Exception as exc:
        print(table, "ERR", exc)
