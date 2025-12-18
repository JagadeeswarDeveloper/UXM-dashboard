import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

def query_audit():
    conn_str = os.getenv("EXPNXT_DB_CONN")
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    print("--- Audit Log ---")
    cursor.execute("SELECT TOP 5 * FROM ExpNXT.load_audit ORDER BY start_ts DESC")
    columns = [column[0] for column in cursor.description]
    print(columns)
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Data Sample ---")
    cursor.execute("SELECT TOP 5 survey_id, ticket_id, happiness_score FROM ExpNXT.RAW_HAPPYSIGNALS_SURVEYS ORDER BY created_date DESC")
    columns = [column[0] for column in cursor.description]
    print(columns)
    for row in cursor.fetchall():
        print(row)

    conn.close()

if __name__ == "__main__":
    query_audit()
