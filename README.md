# HappySignals Ingestion

This project ingests HappySignals survey data from Excel into the `ExpNXT.RAW_HAPPYSIGNALS_SURVEYS` table in SQL Server.

## Prerequisites

- Python 3.8+
- ODBC Driver 18 for SQL Server

## Installation

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   Create a `.env` file in the root directory with your database connection string:
   ```
   EXPNXT_DB_CONN="Driver={ODBC Driver 18 for SQL Server};Server=tcp:yourserver.database.windows.net,1433;Database=db_pt;UID=youruser;PWD=yourpassword;Encrypt=yes;TrustServerCertificate=yes;"
   ```
   
   **Test Connection String (Example):**
   ```
   EXPNXT_DB_CONN="Driver={ODBC Driver 18 for SQL Server};Server=tcp:jabinserver.database.windows.net,1433;Database=db_pt;UID=jabin;PWD=Jemuel@2025;Encrypt=True;TrustServerCertificate=True;"
   ```

## Database Setup

1. Create the Audit Table:
   Run the SQL script `sql/create_load_audit_table.sql` in your database.

2. Create the Stored Procedure:
   Run the SQL script `sql/usp_upsert_happysignals_batch.sql` in your database.

## Usage

### Dry Run (Validation Only)
To check the file and see validation stats without writing to the database:
```bash
python ingest_happysignals.py --input sample_happysignals.xlsx --mode dry-run
```

### Full Load
To ingest the data:
```bash
python ingest_happysignals.py --input sample_happysignals.xlsx --mode run
```

### Options
- `--input`: Path to the Excel file (Required).
- `--sheet`: Sheet name (Optional).
- `--mode`: `dry-run` or `run` (Default: `run`).
- `--chunk-size`: Number of rows per batch (Default: 5000).
- `--log-level`: `INFO` or `DEBUG` (Default: `INFO`).

## Testing

Run the unit tests using pytest:
```bash
pytest tests/
```

## Scheduling

To schedule this script (e.g., via Cron or ADF Custom Activity):
1. Ensure the environment variables are available to the runner.
2. Run the command: `python /path/to/ingest_happysignals.py --input /path/to/file.xlsx`

## Audit Logs

Check the `ExpNXT.load_audit` table for execution history:
```sql
SELECT * FROM ExpNXT.load_audit ORDER BY start_ts DESC;
```
