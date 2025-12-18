import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

def apply_sql_file(cursor, file_path):
    print(f"Applying {file_path}...")
    with open(file_path, 'r') as f:
        sql = f.read()
        # Split by GO if necessary, but pyodbc might not handle GO. 
        # SQL Server Management Studio uses GO as a batch separator, not T-SQL itself.
        # We need to split by GO manually.
        batches = sql.split('GO')
        for batch in batches:
            if batch.strip():
                try:
                    cursor.execute(batch)
                    print("Batch executed.")
                except Exception as e:
                    print(f"Error executing batch: {e}")
                    raise

def main():
    conn_str = os.getenv("EXPNXT_DB_CONN")
    if not conn_str:
        print("Error: EXPNXT_DB_CONN not found.")
        return

    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Apply Audit Table
        apply_sql_file(cursor, "sql/create_load_audit_table.sql")
        
        # Apply Stored Procedure
        # apply_sql_file(cursor, "sql/usp_upsert_happysignals_batch.sql")

        # Apply Table DDL
        apply_sql_file(cursor, "sql/create_raw_esg_metrics.sql")

        # Apply EPEAT Audit Table
        apply_sql_file(cursor, "sql/create_esg_load_audit_table.sql")

        # Apply EPEAT Stored Procedure
        apply_sql_file(cursor, "sql/usp_upsert_epeat_batch.sql")

        conn.commit()
        print("Database schema updated successfully.")
        conn.close()
    except Exception as e:
        print(f"Failed to connect or update DB: {e}")

if __name__ == "__main__":
    main()
