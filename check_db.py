import sqlite3
import pandas as pd
from datetime import datetime

def check_status():
    conn = sqlite3.connect('ci_cd_monitor.db')
    
    # Print summary of failures
    print("\n--- Failure Summary ---")
    query = "SELECT status, COUNT(*) as count FROM failures GROUP BY status"
    df = pd.read_sql_query(query, conn)
    print(df)
    
    # Print recent failures and their reasons
    print("\n--- Recent Failures ---")
    query = "SELECT repository, branch, failure_reason, status FROM failures ORDER BY created_at DESC LIMIT 5"
    df = pd.read_sql_query(query, conn)
    print(df)
    
    conn.close()

if __name__ == "__main__":
    try:
        check_status()
    except Exception as e:
        print(f"Error checking database: {e}")
