import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

def apply_sql_file(cursor, file_path):
    print(f"Applying {file_path}...")
    with open(file_path, 'r') as f:
        sql = f.read()
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

        # Apply HappySignals Stored Procedure
        apply_sql_file(cursor, "sql/usp_upsert_happysignals_batch.sql")

        conn.commit()
        print("HappySignals stored procedure created successfully.")
        conn.close()
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    main()
