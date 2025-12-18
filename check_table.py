import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()
conn_str = os.getenv("EXPNXT_DB_CONN")
try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'ExpNXT' AND TABLE_NAME = 'RAW_ESG_METRICS'")
    if cursor.fetchone():
        print("EXISTS")
    else:
        print("MISSING")
    conn.close()
except Exception as e:
    print(e)
