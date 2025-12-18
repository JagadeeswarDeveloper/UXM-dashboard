import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

# Connect without specifying database (will connect to master)
base_conn = "Driver={SQL Server};Server=tcp:dbsustainability.database.windows.net,1433;UID=sustainability;PWD=Sql@12345;Encrypt=yes;TrustServerCertificate=yes;"

try:
    print("Step 1: Checking master database...")
    conn = pyodbc.connect(base_conn)
    cursor = conn.cursor()
    
    # Check current database
    cursor.execute("SELECT DB_NAME()")
    current_db = cursor.fetchone()[0]
    print(f"Connected to: {current_db}")
    
    # Check if tables exist in master
    cursor.execute("""
        SELECT TABLE_NAME, 
               (SELECT COUNT(*) FROM [master].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS]) as hs_count,
               (SELECT COUNT(*) FROM [master].[ExpNXT].[RAW_ESG_METRICS]) as esg_count
        FROM [master].INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_SCHEMA = 'ExpNXT'
        AND TABLE_NAME IN ('RAW_HAPPYSIGNALS_SURVEYS', 'RAW_ESG_METRICS')
    """)
    
    result = cursor.fetchone()
    if result:
        print(f"\nData found in master database:")
        print(f"  RAW_HAPPYSIGNALS_SURVEYS: {result[1]} rows")
        print(f"  RAW_ESG_METRICS: {result[2]} rows")
    
    print("\nStep 2: Transferring data to DB_Nexthink...")
    
    # Transfer HappySignals data
    cursor.execute("""
        INSERT INTO [DB_Nexthink].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS]
        SELECT * FROM [master].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS]
        WHERE NOT EXISTS (
            SELECT 1 FROM [DB_Nexthink].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS] dst
            WHERE dst.survey_id = [master].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS].survey_id
        )
    """)
    hs_transferred = cursor.rowcount
    print(f"  Transferred {hs_transferred} HappySignals rows")
    
    # Transfer EPEAT data
    cursor.execute("""
        INSERT INTO [DB_Nexthink].[ExpNXT].[RAW_ESG_METRICS]
        SELECT * FROM [master].[ExpNXT].[RAW_ESG_METRICS]
        WHERE NOT EXISTS (
            SELECT 1 FROM [DB_Nexthink].[ExpNXT].[RAW_ESG_METRICS] dst
            WHERE dst.device_model = [master].[ExpNXT].[RAW_ESG_METRICS].device_model
            AND dst.epeat_rating = [master].[ExpNXT].[RAW_ESG_METRICS].epeat_rating
        )
    """)
    esg_transferred = cursor.rowcount
    print(f"  Transferred {esg_transferred} EPEAT rows")
    
    conn.commit()
    
    print("\nStep 3: Verifying data in DB_Nexthink...")
    cursor.execute("SELECT COUNT(*) FROM [DB_Nexthink].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS]")
    hs_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM [DB_Nexthink].[ExpNXT].[RAW_ESG_METRICS]")
    esg_count = cursor.fetchone()[0]
    
    print(f"  DB_Nexthink.RAW_HAPPYSIGNALS_SURVEYS: {hs_count} rows")
    print(f"  DB_Nexthink.RAW_ESG_METRICS: {esg_count} rows")
    
    print("\n✓ Data transfer complete!")
    
    conn.close()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
