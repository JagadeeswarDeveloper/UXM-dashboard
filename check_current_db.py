import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

# Connection string from .env
conn_str = os.getenv("EXPNXT_DB_CONN")
print(f"Connection string: {conn_str}")
print()

# Parse database from connection string
db_name = "DB_Nexthink"  # From Initial Catalog

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    # Check which database we're connected to
    cursor.execute("SELECT DB_NAME()")
    current_db = cursor.fetchone()[0]
    print(f"Currently connected to database: {current_db}")
    print()
    
    # Check if tables exist in current database
    print("--- Checking for tables in current database ---")
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_SCHEMA = 'ExpNXT' 
        AND TABLE_NAME IN ('RAW_HAPPYSIGNALS_SURVEYS', 'RAW_ESG_METRICS')
        ORDER BY TABLE_NAME
    """)
    
    tables = cursor.fetchall()
    if tables:
        print(f"Found {len(tables)} table(s):")
        for table in tables:
            print(f"  - {table[0]}.{table[1]}")
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}.{table[1]}")
            count = cursor.fetchone()[0]
            print(f"    Row count: {count}")
    else:
        print("No ExpNXT tables found in this database")
    
    conn.close()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
