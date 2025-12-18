import os
import sys
import argparse
import logging
import hashlib
import json
import time
import re
import math
from datetime import datetime, date, timezone

# ... (rest of imports)

# ... inside HappySignalsIngester ...


import pandas as pd
import pyodbc
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
def setup_logging(log_level):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    log_file = os.path.join(log_dir, f"ingest_{timestamp}.log")
    
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info(f"Logging initialized. Writing to {log_file}")

class HappySignalsIngester:
    def __init__(self, db_conn_str, chunk_size=5000, dry_run=False):
        self.db_conn_str = db_conn_str
        self.chunk_size = chunk_size
        self.dry_run = dry_run
        self.audit_id = None
        self.stats = {
            "rows_read": 0,
            "rows_inserted": 0,
            "rows_skipped": 0,
            "rows_failed": 0
        }

    def get_db_connection(self):
        try:
            return pyodbc.connect(self.db_conn_str)
        except Exception as e:
            logging.error(f"Failed to connect to database: {e}")
            raise

    def log_audit_start(self, source_file):
        if self.dry_run:
            logging.info("Dry run: Skipping audit log start.")
            return

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            sql = """
                INSERT INTO ExpNXT.load_audit (source_file, status, start_ts)
                OUTPUT INSERTED.audit_id
                VALUES (?, 'STARTED', GETUTCDATE())
            """
            cursor.execute(sql, source_file)
            self.audit_id = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            logging.info(f"Audit log started with ID: {self.audit_id}")
        except Exception as e:
            logging.error(f"Failed to create audit log entry: {e}")
            # We might want to continue even if audit fails, or stop. 
            # For production, usually better to stop if we can't audit.
            raise

    def log_audit_end(self, status="COMPLETED", error_msg=None):
        if self.dry_run or not self.audit_id:
            return

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            sql = """
                UPDATE ExpNXT.load_audit
                SET rows_read = ?, rows_inserted = ?, rows_skipped = ?, rows_failed = ?,
                    end_ts = GETUTCDATE(), status = ?, error_message = ?
                WHERE audit_id = ?
            """
            cursor.execute(sql, 
                           self.stats["rows_read"], 
                           self.stats["rows_inserted"], 
                           self.stats["rows_skipped"], 
                           self.stats["rows_failed"], 
                           status, 
                           error_msg, 
                           self.audit_id)
            conn.commit()
            conn.close()
            logging.info(f"Audit log updated for ID: {self.audit_id} with status: {status}")
        except Exception as e:
            logging.error(f"Failed to update audit log entry: {e}")

    def generate_survey_id(self, row):
        # Format: HS-{Ticket}-{YYYYMMDDHHMMSS}-{hash_first8}
        ticket = str(row.get('ticket_id', 'UNKNOWN')).strip()
        created = row.get('created_date')
        
        if pd.isnull(created):
            created_str = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        else:
            try:
                created_str = pd.to_datetime(created).strftime("%Y%m%d%H%M%S")
            except:
                created_str = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        
        # Create a deterministic hash based on some unique-ish fields
        # Using Ticket, Created, and maybe Email or Comment snippet
        raw_str = f"{ticket}{created_str}{str(row.get('respondent_email', ''))}{str(row.get('comment', ''))[:20]}"
        hash_val = hashlib.sha256(raw_str.encode('utf-8')).hexdigest()[:8]
        
        return f"HS-{ticket}-{created_str}-{hash_val}"

    def validate_and_normalize(self, df):
        valid_rows = []
        
        for index, row in df.iterrows():
            self.stats["rows_read"] += 1
            
            try:
                # 1. Map fields
                normalized = {}
                
                # Dates
                created_raw = row.get('Created')
                if pd.isnull(created_raw):
                    normalized['created_date'] = datetime.utcnow()
                else:
                    normalized['created_date'] = pd.to_datetime(created_raw)
                
                normalized['load_date'] = row.get('Sent Date')
                if pd.isnull(normalized['load_date']):
                     normalized['load_date'] = datetime.utcnow().date()
                else:
                     normalized['load_date'] = pd.to_datetime(normalized['load_date']).date()

                normalized['ticket_id'] = str(row.get('Ticket', '')).strip()
                normalized['location'] = str(row.get('Location', '')).strip()
                
                # Scores
                score = row.get('Score')
                if pd.isnull(score):
                    logging.warning(f"Row {index}: Missing happiness_score. Marking invalid.")
                    self.stats["rows_failed"] += 1
                    continue
                try:
                    normalized['happiness_score'] = float(score)
                    if not (0 <= normalized['happiness_score'] <= 10):
                        logging.warning(f"Row {index}: happiness_score {normalized['happiness_score']} out of range. Marking invalid.")
                        self.stats["rows_failed"] += 1
                        continue
                except ValueError:
                    logging.warning(f"Row {index}: Invalid happiness_score format. Marking invalid.")
                    self.stats["rows_failed"] += 1
                    continue

                normalized['comment'] = str(row.get('Comment', ''))
                
                # Lost time
                lost_time = row.get('Lost time')
                if pd.isnull(lost_time):
                    normalized['lost_time_minutes'] = 0
                else:
                    try:
                        normalized['lost_time_minutes'] = int(lost_time)
                        if normalized['lost_time_minutes'] < 0:
                             logging.warning(f"Row {index}: lost_time_minutes negative. Marking invalid.")
                             self.stats["rows_failed"] += 1
                             continue
                    except ValueError:
                        logging.warning(f"Row {index}: Invalid lost_time format. Marking invalid.")
                        self.stats["rows_failed"] += 1
                        continue

                # Other fields
                normalized['channel'] = str(row.get('Channel', ''))
                normalized['company'] = str(row.get('Company', ''))
                normalized['country'] = str(row.get('Country', ''))
                normalized['service_ticket_type'] = str(row.get('Ticket Type', ''))
                normalized['enterprise_class'] = str(row.get('Enterprise', ''))
                normalized['department'] = str(row.get('Department', ''))
                normalized['region'] = str(row.get('Region', ''))
                normalized['role'] = str(row.get('Role', ''))
                normalized['top_company'] = str(row.get('Top Comp', ''))
                normalized['sub_company'] = str(row.get('Sub Comp', ''))
                
                # JSON/Factors
                extra = str(row.get('Extra Data', ''))
                tags = str(row.get('Tags', ''))
                factors = {'Extra Data': extra, 'Tags': tags}
                normalized['factors'] = json.dumps(factors)

                # Email
                email = row.get('respondent_email')
                if pd.notnull(email) and str(email).strip():
                    email_str = str(email).strip()
                    # Simple regex for email
                    if re.match(r"[^@]+@[^@]+\.[^@]+", email_str):
                        normalized['respondent_email'] = email_str
                    else:
                        logging.warning(f"Row {index}: Invalid email format '{email_str}'. Setting to NULL.")
                        normalized['respondent_email'] = None
                else:
                    normalized['respondent_email'] = None

                # Optional fields
                normalized['translated_comment'] = None # Not in source
                normalized['burnout_risk_score'] = None # Not in source

                # Survey ID
                # Check if 'survey_id' exists in source, else generate
                if 'survey_id' in row and pd.notnull(row['survey_id']):
                    normalized['survey_id'] = str(row['survey_id']).strip()
                else:
                    normalized['survey_id'] = self.generate_survey_id(normalized)

                valid_rows.append(normalized)

            except Exception as e:
                logging.error(f"Row {index}: Unexpected error during validation: {e}")
                self.stats["rows_failed"] += 1

        return pd.DataFrame(valid_rows)

    def upsert_batch(self, df_batch):
        if df_batch.empty:
            return

        # Custom JSON serializer for dates
        def json_serial(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                # SQL Server DATETIME doesn't support timezone offsets
                # Convert to naive UTC if aware
                if obj.tzinfo is not None:
                    obj = obj.astimezone(timezone.utc).replace(tzinfo=None)
                # Use explicit format compatible with SQL Server DATETIME
                return obj.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(obj, date):
                return obj.strftime("%Y-%m-%d")
            if pd.isna(obj):
                return None
            return str(obj)

        # Convert DataFrame to list of dicts, handling NaNs
        # Note: We don't use df.where(pd.notnull(df), None) here because it might coerce types.
        # Instead we rely on the json_serial to handle NaNs/NaTs if they slip through, 
        # or pre-convert.
        
        records = df_batch.to_dict(orient='records')
        
        # Serialize to JSON
        try:
            json_data = json.dumps(records, default=json_serial)
        except Exception as e:
            logging.error(f"JSON serialization failed: {e}")
            self.stats["rows_failed"] += len(records)
            return

        if self.dry_run:
            logging.info(f"Dry run: Would upsert {len(records)} rows.")
            self.stats["rows_inserted"] += len(records)
            return

        # Retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("EXEC ExpNXT.usp_upsert_happysignals_batch ?", json_data)
                conn.commit()
                conn.close()
                self.stats["rows_inserted"] += len(records)
                logging.info(f"Successfully upserted batch of {len(records)} rows.")
                return
            except pyodbc.Error as e:
                logging.warning(f"Database error on attempt {attempt+1}/{max_retries}: {e}")
                if attempt == max_retries - 1:
                     # Log a snippet of the data to help debug
                     logging.error(f"Failed JSON payload snippet: {json_data[:1000]}")
                time.sleep(2 ** attempt)
            except Exception as e:
                logging.error(f"Unexpected error on attempt {attempt+1}/{max_retries}: {e}")
                time.sleep(2 ** attempt)
        
        logging.error(f"Failed to upsert batch after {max_retries} attempts.")
        self.stats["rows_failed"] += len(records)
        # In a real scenario, we might want to dump the failed batch to a file

    def process(self, input_file, sheet_name=None):
        logging.info(f"Starting processing of {input_file}")
        
        try:
            # Read Excel
            # If sheet_name is None, pandas reads the first sheet by default, which is usually what we want.
            # But let's be explicit if provided.
            if sheet_name:
                df_iter = pd.read_excel(input_file, sheet_name=sheet_name)
            else:
                df_iter = pd.read_excel(input_file)
            
            # If the file is huge, read_excel doesn't support chunksize directly like read_csv.
            # We have to read the whole thing or use openpyxl directly for streaming.
            # Given "Large files: process in chunks", standard pd.read_excel loads all into memory.
            # For true streaming of Excel, we'd need a different approach, but for "chunks" in processing terms:
            
            logging.info(f"File loaded. Total rows: {len(df_iter)}")
            
            self.log_audit_start(input_file)

            # Process in chunks
            total_rows = len(df_iter)
            num_chunks = math.ceil(total_rows / self.chunk_size)
            
            for i in range(num_chunks):
                start_idx = i * self.chunk_size
                end_idx = min((i + 1) * self.chunk_size, total_rows)
                
                chunk_df = df_iter.iloc[start_idx:end_idx]
                logging.info(f"Processing chunk {i+1}/{num_chunks} (Rows {start_idx} to {end_idx})")
                
                valid_df = self.validate_and_normalize(chunk_df)
                self.upsert_batch(valid_df)

            self.log_audit_end(status="COMPLETED")
            logging.info("Processing completed.")
            logging.info(f"Stats: {json.dumps(self.stats, indent=2)}")

        except Exception as e:
            logging.error(f"Fatal error during processing: {e}")
            self.log_audit_end(status="FAILED", error_msg=str(e))
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Ingest HappySignals survey data.")
    parser.add_argument("--input", required=True, help="Path to input Excel file")
    parser.add_argument("--sheet", help="Sheet name to read (optional)")
    parser.add_argument("--mode", choices=["dry-run", "run"], default="run", help="Mode: dry-run or run")
    parser.add_argument("--chunk-size", type=int, default=5000, help="Rows per batch")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args()

    setup_logging(args.log_level)

    db_conn = os.getenv("EXPNXT_DB_CONN")
    if not db_conn and args.mode == "run":
        logging.error("EXPNXT_DB_CONN environment variable not set.")
        sys.exit(1)
    
    # For dry-run, we might not need a real DB connection, but the class expects it.
    # We can pass a dummy if dry-run and no env var, but better to warn.
    if not db_conn:
        db_conn = "DUMMY_CONNECTION_STRING"

    ingester = HappySignalsIngester(db_conn, chunk_size=args.chunk_size, dry_run=(args.mode == "dry-run"))
    ingester.process(args.input, args.sheet)

if __name__ == "__main__":
    main()
