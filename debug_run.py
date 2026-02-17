import sqlite3
conn = sqlite3.connect('ci_cd_monitor.db')
cursor = conn.cursor()
cursor.execute("SELECT failure_id, status, failure_reason FROM failures WHERE workflow_run_id = '21977243160'")
row = cursor.fetchone()
if row:
    print(f"Failure ID: {row[0]}")
    print(f"Status: {row[1]}")
    print(f"Reason: {row[2]}")
    
    cursor.execute("SELECT error_type, category, proposed_fix, reasoning FROM analysis_results WHERE failure_id = ?", (row[0],))
    analysis = cursor.fetchone()
    if analysis:
        print(f"Error Type: {analysis[0]}")
        print(f"Category: {analysis[1]}")
        print(f"Proposed Fix: {analysis[2]}")
        print(f"Reasoning: {analysis[3]}")
else:
    print("Run not found in DB")
conn.close()
