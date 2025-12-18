import pyodbc
import time

# Connection to master database explicitly
master_conn_str = "Driver={SQL Server};Server=tcp:dbsustainability.database.windows.net,1433;Database=master;UID=sustainability;PWD=Sql@12345;Encrypt=yes;TrustServerCertificate=yes;"

# Connection to DB_Nexthink explicitly  
nexthink_conn_str = "Driver={SQL Server};Server=tcp:dbsustainability.database.windows.net,1433;Database=DB_Nexthink;UID=sustainability;PWD=Sql@12345;Encrypt=yes;TrustServerCertificate=yes;"

print("Attempting data transfer from master to DB_Nexthink...")
print("=" * 80)

try:
    # Step 1: Query data from master
    print("\nStep 1: Connecting to master database...")
    master_conn = pyodbc.connect(master_conn_str, timeout=30)
    master_cursor = master_conn.cursor()
    
    print("✓ Connected to master")
    
    # Get HappySignals data
    print("\nStep 2: Reading HappySignals data from master...")
    master_cursor.execute("SELECT * FROM ExpNXT.RAW_HAPPYSIGNALS_SURVEYS")
    hs_data = master_cursor.fetchall()
    hs_columns = [column[0] for column in master_cursor.description]
    print(f"✓ Retrieved {len(hs_data)} HappySignals rows")
    
    # Get EPEAT data
    print("\nStep 3: Reading EPEAT data from master...")
    master_cursor.execute("SELECT * FROM ExpNXT.RAW_ESG_METRICS")
    esg_data = master_cursor.fetchall()
    esg_columns = [column[0] for column in master_cursor.description]
    print(f"✓ Retrieved {len(esg_data)} EPEAT rows")
    
    master_conn.close()
    
    # Step 2: Insert into DB_Nexthink
    print("\nStep 4: Connecting to DB_Nexthink...")
    time.sleep(1)  # Brief pause
    nexthink_conn = pyodbc.connect(nexthink_conn_str, timeout=30)
    nexthink_cursor = nexthink_conn.cursor()
    print("✓ Connected to DB_Nexthink")
    
    # Insert HappySignals
    print("\nStep 5: Inserting HappySignals data...")
    hs_placeholders = ','.join(['?' for _ in hs_columns])
    hs_cols = ','.join(hs_columns)
    hs_sql = f"INSERT INTO ExpNXT.RAW_HAPPYSIGNALS_SURVEYS ({hs_cols}) VALUES ({hs_placeholders})"
    
    hs_inserted = 0
    for row in hs_data:
        try:
            nexthink_cursor.execute(hs_sql, row)
            hs_inserted += 1
        except pyodbc.IntegrityError:
            # Skip duplicates
            pass
    
    nexthink_conn.commit()
    print(f"✓ Inserted {hs_inserted} HappySignals rows (skipped {len(hs_data) - hs_inserted} duplicates)")
    
    # Insert EPEAT
    print("\nStep 6: Inserting EPEAT data...")
    esg_placeholders = ','.join(['?' for _ in esg_columns])
    esg_cols = ','.join(esg_columns)
    esg_sql = f"INSERT INTO ExpNXT.RAW_ESG_METRICS ({esg_cols}) VALUES ({esg_placeholders})"
    
    esg_inserted = 0
    for row in esg_data:
        try:
            nexthink_cursor.execute(esg_sql, row)
            esg_inserted += 1
        except pyodbc.IntegrityError:
            # Skip duplicates
            pass
    
    nexthink_conn.commit()
    print(f"✓ Inserted {esg_inserted} EPEAT rows (skipped {len(esg_data) - esg_inserted} duplicates)")
    
    # Verify
    print("\nStep 7: Verifying data in DB_Nexthink...")
    nexthink_cursor.execute("SELECT COUNT(*) FROM ExpNXT.RAW_HAPPYSIGNALS_SURVEYS")
    final_hs = nexthink_cursor.fetchone()[0]
    nexthink_cursor.execute("SELECT COUNT(*) FROM ExpNXT.RAW_ESG_METRICS")
    final_esg = nexthink_cursor.fetchone()[0]
    
    print(f"  RAW_HAPPYSIGNALS_SURVEYS: {final_hs} rows")
    print(f"  RAW_ESG_METRICS: {final_esg} rows")
    
    nexthink_conn.close()
    
    print("\n" + "=" * 80)
    print("✓✓✓ TRANSFER COMPLETE ✓✓✓")
    print("=" * 80)

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
