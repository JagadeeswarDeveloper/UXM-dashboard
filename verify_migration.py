import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()
conn_str = os.getenv("EXPNXT_DB_CONN")

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    print("=== Connection Info ===")
    print(f"Server: {conn_str.split(';')[1]}")
    print(f"Database: {conn_str.split(';')[2]}")

    # Check HappySignals
    cursor.execute("SELECT COUNT(*) FROM ExpNXT.RAW_HAPPYSIGNALS_SURVEYS")
    hs_count = cursor.fetchone()[0]
    print(f"\n=== HappySignals Surveys ===")
    print(f"Row count: {hs_count}")
    
    if hs_count > 0:
        cursor.execute("SELECT TOP 3 survey_id, ticket_id, happiness_score FROM ExpNXT.RAW_HAPPYSIGNALS_SURVEYS")
        for row in cursor.fetchall():
            print(row)

    # Check EPEAT
    cursor.execute("SELECT COUNT(*) FROM ExpNXT.RAW_ESG_METRICS")
    epeat_count = cursor.fetchone()[0]
    print(f"\n=== ESG Metrics (EPEAT) ===")
    print(f"Row count: {epeat_count}")
    
    if epeat_count > 0:
        cursor.execute("SELECT TOP 3 device_model, epeat_rating FROM ExpNXT.RAW_ESG_METRICS")
        for row in cursor.fetchall():
            print(row)

    conn.close()
    print("\n✓ Migration successful!")

except Exception as e:
    print(f"Error: {e}")
