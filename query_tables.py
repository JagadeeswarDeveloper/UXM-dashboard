import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()
conn_str = os.getenv("EXPNXT_DB_CONN")

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("DATABASE: DB_Nexthink @ dbsustainability.database.windows.net")
    print("=" * 80)

    # Query 1: HappySignals Surveys
    print("\n--- ExpNXT.RAW_HAPPYSIGNALS_SURVEYS ---")
    cursor.execute("""
        SELECT TOP 10 
            survey_id, 
            ticket_id, 
            happiness_score, 
            location, 
            department,
            created_date
        FROM ExpNXT.RAW_HAPPYSIGNALS_SURVEYS 
        ORDER BY created_date DESC
    """)
    
    print(f"\nColumns: survey_id | ticket_id | happiness_score | location | department | created_date")
    print("-" * 80)
    for row in cursor.fetchall():
        print(f"{row[0][:30]:30} | {row[1]:12} | {row[2]:15} | {str(row[3])[:15]:15} | {str(row[4])[:15]:15} | {row[5]}")
    
    # Get count
    cursor.execute("SELECT COUNT(*) FROM ExpNXT.RAW_HAPPYSIGNALS_SURVEYS")
    count = cursor.fetchone()[0]
    print(f"\nTotal rows: {count}")

    # Query 2: ESG Metrics
    print("\n\n--- ExpNXT.RAW_ESG_METRICS ---")
    cursor.execute("""
        SELECT TOP 10 
            device_model, 
            epeat_rating, 
            material_composition,
            load_date
        FROM ExpNXT.RAW_ESG_METRICS 
        ORDER BY load_date DESC
    """)
    
    print(f"\nColumns: device_model | epeat_rating | material_composition (truncated) | load_date")
    print("-" * 80)
    for row in cursor.fetchall():
        mat_comp = str(row[2])[:40] if row[2] else "None"
        print(f"{str(row[0])[:35]:35} | {str(row[1]):12} | {mat_comp:40} | {row[3]}")
    
    # Get count
    cursor.execute("SELECT COUNT(*) FROM ExpNXT.RAW_ESG_METRICS")
    count = cursor.fetchone()[0]
    print(f"\nTotal rows: {count}")

    conn.close()
    print("\n" + "=" * 80)
    print("✓ Data verified successfully in both tables!")
    print("=" * 80)

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
