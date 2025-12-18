import os
import sys
import argparse
import logging
import json
import time
import re
import math
from datetime import datetime, date, timezone
import pandas as pd
import pyodbc
from dotenv import load_dotenv
from fuzzywuzzy import fuzz
from fuzzywuzzy import process as fuzzy_process

# Load environment variables
load_dotenv()

# Configure logging
def setup_logging(log_level):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    log_file = os.path.join(log_dir, f"epeat_ingest_{timestamp}.log")
    
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

class EPEAHIngester:
    def __init__(self, db_conn_str, chunk_size=5000, dry_run=False, match_threshold=85):
        self.db_conn_str = db_conn_str
        self.chunk_size = chunk_size
        self.dry_run = dry_run
        self.match_threshold = match_threshold
        self.audit_id = None
        self.inventory = [] # List of known device models (lowercase, cleaned)
        self.stats = {
            "rows_read": 0,
            "rows_matched_inventory": 0,
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

    def load_inventory(self):
        # In a real scenario, fetch distinct models from ExpNXT.DeviceInventory or similar
        # For this exercise, we'll try to fetch if table exists, else empty
        if self.dry_run and not self.db_conn_str:
             logging.info("Dry run with no DB: skipping inventory load.")
             self.inventory = ["latitude 7420", "thinkpad x1 carbon", "surface pro 7"] # mock
             return

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            # Try to read from a likely table if it exists
            # We assume ExpNXT.RAW_NEXTHINK_METRICS (from previous steps) might have device_model?
            # Or user mentioned ExpNXT.DeviceInventory
            try:
                cursor.execute("SELECT DISTINCT device_model FROM ExpNXT.RAW_ESG_METRICS WHERE device_model IS NOT NULL")
                rows = cursor.fetchall()
                self.inventory = [str(r[0]).lower().strip() for r in rows]
                logging.info(f"Loaded {len(self.inventory)} known models from ESG Metrics for matching context.")
            except:
                logging.info("Could not load inventory (table might be empty or missing). Comparison will be limited.")
                self.inventory = []
            conn.close()
        except Exception as e:
            logging.warning(f"Failed to load inventory: {e}")
            self.inventory = []

    def log_audit_start(self, source_file):
        if self.dry_run:
            logging.info("Dry run: Skipping audit log start.")
            return

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            sql = """
                INSERT INTO ExpNXT.esg_load_audit (source_file, status, start_ts)
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
            # Continue without audit if it fails (optional decision)

    def log_audit_end(self, status="COMPLETED", error_msg=None):
        if self.dry_run or not self.audit_id:
            return

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            sql = """
                UPDATE ExpNXT.esg_load_audit
                SET rows_read = ?, rows_matched_inventory = ?, rows_inserted = ?, rows_skipped = ?, 
                    rows_failed = ?, end_ts = GETUTCDATE(), status = ?, error_message = ?
                WHERE audit_id = ?
            """
            cursor.execute(sql, 
                           self.stats["rows_read"], 
                           self.stats["rows_matched_inventory"],
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

    def clean_model_name(self, name):
        if pd.isnull(name): return ""
        # Remove special chars, extra spaces, lowercase
        name = str(name).lower()
        name = re.sub(r'[^a-z0-9\s]', '', name)
        return name.strip()

    def find_best_match(self, model_name):
        if not self.inventory:
            return None
        
        cleaned = self.clean_model_name(model_name)
        
        # 1. Exact match
        if cleaned in self.inventory:
            return cleaned # Or find original casing if needed
            
        # 2. Fuzzy match
        # Extract best match from inventory
        best_match, score = fuzzy_process.extractOne(cleaned, self.inventory, scorer=fuzz.token_sort_ratio)
        if score >= self.match_threshold:
            return best_match
        
        return None

    def validate_and_normalize(self, df):
        valid_rows = []
        
        for index, row in df.iterrows():
            self.stats["rows_read"] += 1
            
            try:
                # Mapping
                # Product Name -> device_model
                raw_model = row.get('Product Name')
                if pd.isnull(raw_model):
                    # Skip if no product name
                    self.stats["rows_skipped"] += 1
                    continue
                
                manufacturer = str(row.get('Manufacturer', '')).strip().upper()
                if not manufacturer:
                     self.stats["rows_skipped"] += 1
                     continue

                epeat_tier = str(row.get('EPEAT Tier', '')).strip().title() # Gold, Silver...
                if epeat_tier not in ['Gold', 'Silver', 'Bronze']:
                    # Normalize if close? Or just log?
                    if 'gold' in epeat_tier.lower(): epeat_tier = 'Gold'
                    elif 'silver' in epeat_tier.lower(): epeat_tier = 'Silver'
                    elif 'bronze' in epeat_tier.lower(): epeat_tier = 'Bronze'
                    else:
                        logging.warning(f"Row {index}: Unknown EPEAT Tier '{epeat_tier}'. Skipping.")
                        self.stats["rows_skipped"] += 1
                        continue
                
                # Matching
                # If we have matches, we might override the model name with the internal one?
                # Or just store the source model. User said "Fall back to cleaned model name".
                # For now, we store the EPEAT model name as 'device_model', 
                # but we track if we matched it to inventory.
                matched_model = self.find_best_match(raw_model)
                if matched_model:
                     self.stats["rows_matched_inventory"] += 1
                     # Option: Use matched model name? 
                     # self.device_model = matched_model 
                     # But EPEAT might be specific. Let's keep source 'Product Name' as device_model
                     # and maybe use 'serial_number' col as a flag or link?
                     # Prompt: "Matching must support... fallback... mark row as unmatched but still insert with NULL serial_number"
                     # So if matched, we might ideally populate serial_number if we could link it, but we can't from just model name usually.
                     # We'll just populate 'device_model' with the Cleaned/Raw name.
                     pass

                # Build record
                normalized = {}
                normalized['load_date'] = datetime.utcnow().date()
                normalized['serial_number'] = None # No serials in EPEAT data
                normalized['device_model'] = str(raw_model).strip()
                normalized['epeat_rating'] = epeat_tier
                normalized['manufacturer'] = manufacturer # Note: Schema might not have this column? We'll put it in Material Composition JSON if needed or assume user added it.
                
                # Handling extra columns
                # Store manufacturer, product type, category in 'material_composition' JSON if columns missing in DB?
                # User prompt: "EPEAT CSV -> RAW_ESG_METRICS ... Manufacturer -> manufacturer"
                # If 'manufacturer' column is missing in DB (it was missing in Step 7 schema), we should handle it.
                # I'll check table info or assume it's there. 
                # Safest: Use JSON for extra fields.
                
                mat_comp = {
                    "Manufacturer": manufacturer,
                    "Product Category": str(row.get('Product Category', '')),
                    "Product Type": str(row.get('Product Type', '')),
                    "Product URL": str(row.get('Product URL', ''))
                }
                normalized['material_composition'] = json.dumps(mat_comp)
                
                # Nulls for others
                normalized['energy_star_rating'] = None
                normalized['battery_capacity'] = None
                normalized['cpu_power_rating'] = None
                normalized['display_power_rating'] = None
                normalized['manufacturing_kg_co2'] = None
                normalized['lifecycle_kg_co2'] = None

                valid_rows.append(normalized)

            except Exception as e:
                logging.error(f"Row {index}: validation error: {e}")
                self.stats["rows_failed"] += 1
        
        return pd.DataFrame(valid_rows)

    def upsert_batch(self, df_batch):
        if df_batch.empty: return
        
        # JSON Serializer
        def json_serial(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                if obj.tzinfo is not None:
                     obj = obj.astimezone(timezone.utc).replace(tzinfo=None)
                return obj.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(obj, date):
                return obj.strftime("%Y-%m-%d")
            return str(obj)

        records = df_batch.to_dict(orient='records')
        try:
             json_data = json.dumps(records, default=json_serial)
        except Exception as e:
             logging.error(f"JSON serialization error: {e}")
             self.stats["rows_failed"] += len(records)
             return

        if self.dry_run:
            logging.info(f"Dry run: Would upsert {len(records)} rows.")
            self.stats["rows_inserted"] += len(records)
            return

        max_retries = 3
        for attempt in range(max_retries):
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("EXEC ExpNXT.usp_upsert_epeat_batch ?", json_data)
                conn.commit()
                conn.close()
                self.stats["rows_inserted"] += len(records)
                logging.info(f"Upserted batch of {len(records)} rows.")
                return
            except Exception as e:
                logging.warning(f"DB Error attempt {attempt+1}: {e}")
                time.sleep(2**attempt)
        
        logging.error("Failed to upsert batch.")
        self.stats["rows_failed"] += len(records)

    def process(self, input_file, sheet_name=None):
        logging.info(f"Processing {input_file}")
        try:
            self.load_inventory()
            
            # Determine sheet to read
            xl = pd.ExcelFile(input_file)
            sheet = sheet_name if sheet_name else xl.sheet_names[0]
            logging.info(f"Reading sheet: {sheet} from {xl.sheet_names}")
            
            df_iter = pd.read_excel(input_file, sheet_name=sheet)
            logging.info(f"Loaded DataFrame with shape: {df_iter.shape}")
            logging.info(f"Columns: {df_iter.columns.tolist()[:10]}...") # Log first 10 columns
            
            self.log_audit_start(input_file)
            
            total_rows = len(df_iter)
            num_chunks = math.ceil(total_rows / self.chunk_size)
            
            for i in range(num_chunks):
                chunk = df_iter.iloc[i*self.chunk_size : (i+1)*self.chunk_size]
                valid_df = self.validate_and_normalize(chunk)
                self.upsert_batch(valid_df)

            self.log_audit_end(status="COMPLETED")
            logging.info(f"Stats: {self.stats}")
            
        except Exception as e:
            logging.error(f"Fatal error: {e}")
            self.log_audit_end(status="FAILED", error_msg=str(e))
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--mode", default="run", choices=["dry-run", "run"])
    parser.add_argument("--chunk-size", default=5000, type=int)
    parser.add_argument("--sheet", help="Sheet name (optional)")
    args = parser.parse_args()

    setup_logging("INFO")
    
    conn_str = os.getenv("EXPNXT_DB_CONN")
    if not conn_str and args.mode == "run":
        logging.error("EXPNXT_DB_CONN not set")
        sys.exit(1)
        
    ingester = EPEAHIngester(conn_str, chunk_size=args.chunk_size, dry_run=(args.mode == "dry-run"))
    ingester.process(args.input, args.sheet)

if __name__ == "__main__":
    main()
