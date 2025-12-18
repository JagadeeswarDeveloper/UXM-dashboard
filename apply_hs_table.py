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

def main():
    conn_str = os.getenv("EXPNXT_DB_CONN")
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    apply_sql_file(cursor, "sql/create_raw_happysignals_surveys.sql")

    conn.commit()
    print("Table created successfully.")
    conn.close()

if __name__ == "__main__":
    main()
