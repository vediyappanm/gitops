import sqlite3
import sys

fid = sys.argv[1]
conn = sqlite3.connect('ci_cd_monitor.db')
cursor = conn.cursor()
cursor.execute("SELECT logs, failure_reason FROM failures WHERE failure_id=?", (fid,))
row = cursor.fetchone()
if row:
    print(f"REASON: {row[1]}")
    print(f"LOGS: {row[0][:1000]}")
else:
    print("Not found")
conn.close()
