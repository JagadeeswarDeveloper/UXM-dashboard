import os
import sys
import argparse
import logging
import json
import time
import re
import hashlib
import math
from datetime import datetime, date, timezone
import pandas as pd
import pyodbc
from dotenv import load_dotenv
from fuzzywuzzy import fuzz
from fuzzywuzzy import process as fuzzy_process

# Load environment variables
load_dotenv()

class BaseIngester:
    def __init__(self, db_conn_str, dry_run=False):
        self.db_conn_str = db_conn_str
        self.dry_run = dry_run
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

    def apply_schema(self, sql_dir="sql"):
        """Ensure all required tables and stored procedures exist."""
        if self.dry_run:
            logging.info("Dry run: Skipping schema application.")
            return

        logging.info("Checking and applying schema...")
        files_to_apply = [
            "create_load_audit_table.sql",
            "create_esg_load_audit_table.sql",
            "create_raw_happysignals_surveys.sql",
            "create_raw_esg_metrics.sql",
            "usp_upsert_happysignals_batch.sql",
            "usp_upsert_epeat_batch.sql"
        ]

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            for filename in files_to_apply:
                file_path = os.path.join(sql_dir, filename)
                if not os.path.exists(file_path):
                    logging.warning(f"Schema file not found: {file_path}")
                    continue

                logging.info(f"Applying {file_path}...")
                with open(file_path, 'r') as f:
                    sql = f.read()
                    # Split by GO for SQL Server batches
                    batches = re.split(r'(?i)^\s*GO\s*$', sql, flags=re.MULTILINE)
                    for batch in batches:
                        if batch.strip():
                            try:
                                cursor.execute(batch)
                            except Exception as e:
                                # If it's an "already exists" error, we might ignore it depending on the SQL logic
                                if "already an object named" in str(e) or "already exists" in str(e).lower():
                                    logging.debug(f"Object already exists in {filename}: {str(e)[:100]}...")
                                else:
                                    logging.error(f"Error executing batch in {filename}: {e}")
                                    raise
            conn.commit()
            conn.close()
            logging.info("Schema verification/application complete.")
        except Exception as e:
            logging.error(f"Schema application failed: {e}")
            raise

    def json_serial(self, obj):
        """Custom JSON serializer for dates."""
        if isinstance(obj, (datetime, pd.Timestamp)):
            if obj.tzinfo is not None:
                obj = obj.astimezone(timezone.utc).replace(tzinfo=None)
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        if pd.isna(obj):
            return None
        return str(obj)

class HappySignalsIngester(BaseIngester):
    def __init__(self, db_conn_str, dry_run=False, chunk_size=5000):
        super().__init__(db_conn_str, dry_run)
        self.chunk_size = chunk_size
        self.audit_id = None

    def generate_survey_id(self, ticket_id, created_date, email):
        """Generate a deterministic survey ID."""
        date_str = pd.to_datetime(created_date).strftime("%Y%m%d%H%M%S")
        unique_str = f"{ticket_id}-{date_str}-{email}"
        hash_val = hashlib.md5(unique_str.encode()).hexdigest()[:8]
        return f"HS-{ticket_id}-{date_str}-{hash_val}"

    def validate_and_normalize(self, df):
        valid_rows = []
        for index, row in df.iterrows():
            self.stats["rows_read"] += 1
            try:
                ticket_id = str(row.get('Ticket', '')).strip()
                if not ticket_id: continue

                created_raw = row.get('Created')
                created_date = pd.to_datetime(created_raw) if not pd.isnull(created_raw) else datetime.utcnow()
                
                email = str(row.get('Respondent email', '')).strip().lower()

                normalized = {
                    "load_date": datetime.utcnow().date(),
                    "survey_id": self.generate_survey_id(ticket_id, created_date, email),
                    "respondent_email": email,
                    "ticket_id": ticket_id,
                    "happiness_score": float(row.get('Score', 0)),
                    "lost_time_minutes": int(row.get('Lost time', 0)) if not pd.isnull(row.get('Lost time')) else 0,
                    "factors": str(row.get('Factors', '')),
                    "comment": str(row.get('Comment', '')),
                    "translated_comment": str(row.get('Comment', '')), # Placeholder for translation logic
                    "department": str(row.get('Department', '')),
                    "location": str(row.get('Location', '')),
                    "country": str(row.get('Country', '')),
                    "role": str(row.get('Role', '')),
                    "region": str(row.get('Region', '')),
                    "channel": str(row.get('Channel', '')),
                    "service_ticket_type": str(row.get('Ticket type', '')),
                    "enterprise_class": str(row.get('Enterprise class', '')),
                    "burnout_risk_score": float(row.get('Burnout risk', 0)) if not pd.isnull(row.get('Burnout risk')) else 0,
                    "company": str(row.get('Company', '')),
                    "top_company": str(row.get('Top company', '')),
                    "sub_company": str(row.get('Sub company', '')),
                    "created_date": created_date
                }
                valid_rows.append(normalized)
            except Exception as e:
                logging.error(f"HS Row {index} validation error: {e}")
                self.stats["rows_failed"] += 1
        return pd.DataFrame(valid_rows)

    def log_audit_start(self, source_file):
        if self.dry_run: return
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            sql = "INSERT INTO ExpNXT.load_audit (source_file, status, start_ts) OUTPUT INSERTED.audit_id VALUES (?, 'STARTED', GETUTCDATE())"
            cursor.execute(sql, source_file)
            self.audit_id = cursor.fetchone()[0]
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"HS Audit start failed: {e}")

    def log_audit_end(self, status="COMPLETED"):
        if self.dry_run or not self.audit_id: return
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            sql = "UPDATE ExpNXT.load_audit SET rows_read=?, rows_inserted=?, rows_skipped=?, rows_failed=?, end_ts=GETUTCDATE(), status=? WHERE audit_id=?"
            cursor.execute(sql, self.stats["rows_read"], self.stats["rows_inserted"], self.stats["rows_skipped"], self.stats["rows_failed"], status, self.audit_id)
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"HS Audit end failed: {e}")

    def upsert_batch(self, df_batch):
        if df_batch.empty: return
        records = df_batch.to_dict(orient='records')
        json_data = json.dumps(records, default=self.json_serial)

        if self.dry_run:
            self.stats["rows_inserted"] += len(records)
            return

        for attempt in range(3):
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("EXEC ExpNXT.usp_upsert_happysignals_batch ?", json_data)
                conn.commit()
                conn.close()
                self.stats["rows_inserted"] += len(records)
                return
            except Exception as e:
                logging.warning(f"HS Upsert attempt {attempt+1} failed: {e}")
                time.sleep(2**attempt)
        self.stats["rows_failed"] += len(records)

    def process(self, input_file):
        logging.info(f"Processing HappySignals file: {input_file}")
        try:
            df = pd.read_excel(input_file)
            self.log_audit_start(input_file)
            
            num_chunks = math.ceil(len(df) / self.chunk_size)
            for i in range(num_chunks):
                chunk = df.iloc[i * self.chunk_size : (i + 1) * self.chunk_size]
                valid_df = self.validate_and_normalize(chunk)
                self.upsert_batch(valid_df)
            
            self.log_audit_end()
            logging.info(f"HappySignals Stats: {self.stats}")
        except Exception as e:
            logging.error(f"HappySignals processing failed: {e}")
            self.log_audit_end("FAILED")

class EPEATIngester(BaseIngester):
    def __init__(self, db_conn_str, dry_run=False, chunk_size=5000, match_threshold=85):
        super().__init__(db_conn_str, dry_run)
        self.chunk_size = chunk_size
        self.match_threshold = match_threshold
        self.audit_id = None
        self.inventory = []
        self.stats["rows_matched_inventory"] = 0

    def load_inventory(self):
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT device_model FROM ExpNXT.RAW_ESG_METRICS WHERE device_model IS NOT NULL")
            self.inventory = [str(r[0]).lower().strip() for r in cursor.fetchall()]
            conn.close()
        except:
            self.inventory = []

    def find_best_match(self, model_name):
        if not self.inventory: return None
        cleaned = re.sub(r'[^a-z0-9\s]', '', str(model_name).lower()).strip()
        if cleaned in self.inventory: return cleaned
        best_match, score = fuzzy_process.extractOne(cleaned, self.inventory, scorer=fuzz.token_sort_ratio)
        return best_match if score >= self.match_threshold else None

    def validate_and_normalize(self, df):
        valid_rows = []
        for index, row in df.iterrows():
            self.stats["rows_read"] += 1
            try:
                raw_model = row.get('Product Name')
                manufacturer = str(row.get('Manufacturer', '')).strip().upper()
                if pd.isnull(raw_model) or not manufacturer: 
                    self.stats["rows_skipped"] += 1
                    continue

                epeat_tier = str(row.get('EPEAT Tier', '')).strip().title()
                if 'Gold' in epeat_tier: epeat_tier = 'Gold'
                elif 'Silver' in epeat_tier: epeat_tier = 'Silver'
                elif 'Bronze' in epeat_tier: epeat_tier = 'Bronze'
                else:
                    self.stats["rows_skipped"] += 1
                    continue

                if self.find_best_match(raw_model):
                    self.stats["rows_matched_inventory"] += 1

                normalized = {
                    "load_date": datetime.utcnow().date(),
                    "serial_number": None,
                    "device_model": str(raw_model).strip(),
                    "epeat_rating": epeat_tier,
                    "energy_star_rating": None,
                    "material_composition": json.dumps({
                        "Manufacturer": manufacturer,
                        "Category": str(row.get('Product Category', '')),
                        "Type": str(row.get('Product Type', '')),
                        "URL": str(row.get('Product URL', ''))
                    }),
                    "battery_capacity": None,
                    "cpu_power_rating": None,
                    "display_power_rating": None,
                    "manufacturing_kg_co2": None,
                    "lifecycle_kg_co2": None
                }
                valid_rows.append(normalized)
            except Exception as e:
                logging.error(f"EPEAT Row {index} validation error: {e}")
                self.stats["rows_failed"] += 1
        return pd.DataFrame(valid_rows)

    def log_audit_start(self, source_file):
        if self.dry_run: return
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            sql = "INSERT INTO ExpNXT.esg_load_audit (source_file, status, start_ts) OUTPUT INSERTED.audit_id VALUES (?, 'STARTED', GETUTCDATE())"
            cursor.execute(sql, source_file)
            self.audit_id = cursor.fetchone()[0]
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"EPEAT Audit start failed: {e}")

    def log_audit_end(self, status="COMPLETED"):
        if self.dry_run or not self.audit_id: return
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            sql = """UPDATE ExpNXT.esg_load_audit SET rows_read=?, rows_matched_inventory=?, rows_inserted=?, rows_skipped=?, rows_failed=?, end_ts=GETUTCDATE(), status=? WHERE audit_id=?"""
            cursor.execute(sql, self.stats["rows_read"], self.stats["rows_matched_inventory"], self.stats["rows_inserted"], self.stats["rows_skipped"], self.stats["rows_failed"], status, self.audit_id)
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"EPEAT Audit end failed: {e}")

    def upsert_batch(self, df_batch):
        if df_batch.empty: return
        records = df_batch.to_dict(orient='records')
        json_data = json.dumps(records, default=self.json_serial)

        if self.dry_run:
            self.stats["rows_inserted"] += len(records)
            return

        for attempt in range(3):
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("EXEC ExpNXT.usp_upsert_epeat_batch ?", json_data)
                conn.commit()
                conn.close()
                self.stats["rows_inserted"] += len(records)
                return
            except Exception as e:
                logging.warning(f"EPEAT Upsert attempt {attempt+1} failed: {e}")
                time.sleep(2**attempt)
        self.stats["rows_failed"] += len(records)

    def process(self, input_file, sheet_name=None):
        logging.info(f"Processing EPEAT file: {input_file} (sheet: {sheet_name})")
        try:
            self.load_inventory()
            df = pd.read_excel(input_file, sheet_name=sheet_name)
            self.log_audit_start(input_file)
            
            num_chunks = math.ceil(len(df) / self.chunk_size)
            for i in range(num_chunks):
                chunk = df.iloc[i * self.chunk_size : (i + 1) * self.chunk_size]
                valid_df = self.validate_and_normalize(chunk)
                self.upsert_batch(valid_df)
            
            self.log_audit_end()
            logging.info(f"EPEAT Stats: {self.stats}")
        except Exception as e:
            logging.error(f"EPEAT processing failed: {e}")
            self.log_audit_end("FAILED")

def setup_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir): os.makedirs(log_dir)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    log_file = os.path.join(log_dir, f"unified_ingest_{ts}.log")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)])
    logging.info(f"Unified Ingestion started. Logs: {log_file}")

def main():
    parser = argparse.ArgumentParser(description="Unified Ingestion Pipeline")
    parser.add_argument("--hs-input", help="HappySignals Excel file path")
    parser.add_argument("--epeat-input", help="EPEAT Excel file path")
    parser.add_argument("--epeat-sheet", default="EPEAT 2.0", help="EPEAT sheet name")
    parser.add_argument("--mode", default="run", choices=["run", "dry-run"])
    parser.add_argument("--skip-schema", action="store_true", help="Skip schema application")
    args = parser.parse_args()

    setup_logging()
    conn_str = os.getenv("EXPNXT_DB_CONN")
    if not conn_str:
        logging.error("EXPNXT_DB_CONN environment variable not set.")
        sys.exit(1)

    base = BaseIngester(conn_str, dry_run=(args.mode == "dry-run"))
    
    if not args.skip_schema:
        base.apply_schema()

    if args.hs_input:
        hs = HappySignalsIngester(conn_str, dry_run=(args.mode == "run" and False or args.mode == "dry-run"))
        hs.process(args.hs_input)
        
    if args.epeat_input:
        epeat = EPEATIngester(conn_str, dry_run=(args.mode == "run" and False or args.mode == "dry-run"))
        epeat.process(args.epeat_input, args.epeat_sheet)

    logging.info("Unified Ingestion Finished.")

if __name__ == "__main__":
    main()
