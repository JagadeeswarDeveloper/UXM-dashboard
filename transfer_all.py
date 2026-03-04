"""
Consolidated transfer script that reads data from a source DB (master) and
inserts into the target DB (DB_Nexthink). Supports --dry-run and environment
configuration to avoid hard-coded credentials.

Functions are written to be unit-testable (pyodbc can be mocked in tests).
"""
import os
import argparse
import logging
from typing import List, Tuple

try:
    import pyodbc
except Exception:
    pyodbc = None  # Tests can mock this


LOG = logging.getLogger("transfer_all")


def get_conn(conn_str: str):
    if pyodbc is None:
        raise RuntimeError("pyodbc not available - are you running in a test?")
    return pyodbc.connect(conn_str, timeout=30)


def fetch_table(conn_str: str, table: str) -> Tuple[List[str], List[tuple]]:
    """Fetch all rows from the given fully-qualified table.
    Returns (columns, rows)
    """
    with get_conn(conn_str) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description]
    return cols, rows


def insert_rows(conn_str: str, table: str, cols: List[str], rows: List[tuple], dry_run: bool = True) -> int:
    """Insert rows into the given table. Returns number of rows "inserted".
    When dry_run=True, no DB writes happen; function returns count that would
    have been attempted.
    """
    if dry_run:
        LOG.info("Dry-run enabled: would insert %d rows into %s", len(rows), table)
        return len(rows)

    if not rows:
        return 0

    placeholders = ",".join(["?" for _ in cols])
    cols_sql = ",".join(cols)
    sql = f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders})"

    inserted = 0
    conn = get_conn(conn_str)
    cur = conn.cursor()
    for r in rows:
        try:
            cur.execute(sql, r)
            inserted += 1
        except Exception:
            # Keep it resilient: skip problematic rows
            LOG.exception("Failed inserting row into %s", table)
    conn.commit()
    conn.close()
    return inserted


def count_rows(conn_str: str, table: str) -> int:
    with get_conn(conn_str) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def transfer_table(src_conn: str, dst_conn: str, src_table: str, dst_table: str, dry_run: bool = True):
    cols, rows = fetch_table(src_conn, src_table)
    LOG.info("Fetched %d rows from %s", len(rows), src_table)
    inserted = insert_rows(dst_conn, dst_table, cols, rows, dry_run=dry_run)
    LOG.info("Inserted %d rows into %s", inserted, dst_table)
    return len(rows), inserted


def validate_and_normalize_hs_rows(cols, rows):
    """Take raw rows (list of tuples) and their column names and return list of normalized dicts."""
    import pandas as pd
    import json, re, hashlib
    from datetime import datetime

    df = pd.DataFrame(rows, columns=cols)
    ing_stats = {"rows_read": 0, "rows_failed": 0}
    normalized_records = []

    for idx, row in df.iterrows():
        ing_stats["rows_read"] += 1
        try:
            normalized = {}
            # Created date
            created_raw = row.get('Created') if 'Created' in row else None
            if pd.isnull(created_raw) or created_raw is None:
                created = datetime.utcnow()
            else:
                created = pd.to_datetime(created_raw)
            normalized['created_date'] = created

            # Load date
            load_raw = row.get('Sent Date') if 'Sent Date' in row else None
            if pd.isnull(load_raw) or load_raw is None:
                normalized['load_date'] = datetime.utcnow().date()
            else:
                normalized['load_date'] = pd.to_datetime(load_raw).date()

            normalized['ticket_id'] = str(row.get('Ticket', '')).strip()

            # Score
            score = row.get('Score') if 'Score' in row else None
            if pd.isnull(score) or score is None:
                ing_stats['rows_failed'] += 1
                continue
            try:
                score_val = float(score)
                if not (0 <= score_val <= 10):
                    ing_stats['rows_failed'] += 1
                    continue
                normalized['happiness_score'] = score_val
            except Exception:
                ing_stats['rows_failed'] += 1
                continue

            # Lost time
            lost = row.get('Lost time') if 'Lost time' in row else None
            if pd.isnull(lost) or lost is None:
                normalized['lost_time_minutes'] = 0
            else:
                try:
                    lt = int(lost)
                    if lt < 0:
                        ing_stats['rows_failed'] += 1
                        continue
                    normalized['lost_time_minutes'] = lt
                except Exception:
                    ing_stats['rows_failed'] += 1
                    continue

            # Email
            email = row.get('respondent_email') if 'respondent_email' in row else None
            if pd.notnull(email) and str(email).strip():
                email_str = str(email).strip()
                if re.match(r"[^@]+@[^@]+\.[^@]+", email_str):
                    normalized['respondent_email'] = email_str
                else:
                    normalized['respondent_email'] = None
            else:
                normalized['respondent_email'] = None

            # Comment, company, other fields
            normalized['comment'] = str(row.get('Comment', ''))
            normalized['company'] = str(row.get('Company', ''))

            # Survey id deterministic
            ticket = normalized['ticket_id'] or 'UNKNOWN'
            created_str = normalized['created_date'].strftime('%Y%m%d%H%M%S')
            raw_hash = f"{ticket}{created_str}{normalized.get('respondent_email','')}{normalized.get('comment','')[:20]}"
            normalized['survey_id'] = 'HS-' + ticket + '-' + created_str + '-' + hashlib.sha256(raw_hash.encode('utf-8')).hexdigest()[:8]

            normalized_records.append(normalized)
        except Exception:
            ing_stats['rows_failed'] += 1
            continue

    return normalized_records, ing_stats


def validate_and_normalize_esg_rows(cols, rows):
    """Normalize EPEAT rows to expected fields."""
    import pandas as pd
    import json, re
    from datetime import datetime

    df = pd.DataFrame(rows, columns=cols)
    stats = {"rows_read": 0, "rows_skipped": 0, "rows_failed": 0}
    records = []

    def clean_model(name):
        if pd.isnull(name):
            return ''
        s = str(name).lower()
        s = re.sub(r'[^a-z0-9\s]', '', s)
        return s.strip()

    for idx, row in df.iterrows():
        stats['rows_read'] += 1
        try:
            prod = row.get('Product Name') if 'Product Name' in row else None
            man = row.get('Manufacturer') if 'Manufacturer' in row else ''
            tier = row.get('EPEAT Tier') if 'EPEAT Tier' in row else ''
            if pd.isnull(prod) or not str(prod).strip():
                stats['rows_skipped'] += 1
                continue
            if pd.isnull(man) or not str(man).strip():
                stats['rows_skipped'] += 1
                continue
            tier_norm = str(tier).strip().title()
            if tier_norm not in ['Gold', 'Silver', 'Bronze']:
                # attempt simple normalization
                t = str(tier).lower()
                if 'gold' in t:
                    tier_norm = 'Gold'
                elif 'silver' in t:
                    tier_norm = 'Silver'
                elif 'bronze' in t:
                    tier_norm = 'Bronze'
                else:
                    stats['rows_skipped'] += 1
                    continue

            rec = {}
            rec['device_model'] = str(prod).strip()
            rec['manufacturer'] = str(man).strip()
            rec['epeat_rating'] = tier_norm
            rec['load_date'] = datetime.utcnow().date()
            rec['material_composition'] = json.dumps({'Product Category': row.get('Product Category', ''), 'Product Type': row.get('Product Type', '')})
            records.append(rec)
        except Exception:
            stats['rows_failed'] += 1
            continue

    return records, stats


def upsert_json_payload(dst_conn_str: str, sp_name: str, records: list, dry_run: bool = True) -> int:
    """Send records as JSON to a stored procedure that accepts a single JSON parameter.
    Returns number of records attempted.
    """
    import json
    from datetime import datetime
    if not records:
        return 0
    if dry_run:
        LOG.info("Dry-run: would call %s with %d records", sp_name, len(records))
        return len(records)

    # Prepare JSON serialization for datetimes
    def json_serial(o):
        if hasattr(o, 'strftime'):
            return o.strftime('%Y-%m-%d %H:%M:%S')
        return str(o)

    payload = json.dumps(records, default=json_serial)

    conn = get_conn(dst_conn_str)
    cur = conn.cursor()
    sql = f"EXEC {sp_name} ?"
    cur.execute(sql, payload)
    conn.commit()
    conn.close()
    LOG.info("Executed %s; rows=%d", sp_name, len(records))
    return len(records)


def process_both_from_db(src_conn: str, dst_conn: str, dry_run: bool = True):
    # HappySignals
    hs_table = "[master].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS]"
    hs_cols, hs_rows = fetch_table(src_conn, hs_table)
    hs_recs, hs_stats = validate_and_normalize_hs_rows(hs_cols, hs_rows)
    hs_upserted = upsert_json_payload(dst_conn, 'ExpNXT.usp_upsert_happysignals_batch', hs_recs, dry_run=dry_run)

    # EPEAT/ESG
    esg_table = "[master].[ExpNXT].[RAW_ESG_METRICS]"
    esg_cols, esg_rows = fetch_table(src_conn, esg_table)
    esg_recs, esg_stats = validate_and_normalize_esg_rows(esg_cols, esg_rows)
    esg_upserted = upsert_json_payload(dst_conn, 'ExpNXT.usp_upsert_epeat_batch', esg_recs, dry_run=dry_run)

    LOG.info("HappySignals: fetched=%d validated=%d inserted=%d", len(hs_rows), len(hs_recs), hs_upserted)
    LOG.info("EPEAT: fetched=%d validated=%d inserted=%d", len(esg_rows), len(esg_recs), esg_upserted)

    return {
        'hs': {'fetched': len(hs_rows), 'validated': len(hs_recs), 'upserted': hs_upserted, **hs_stats},
        'esg': {'fetched': len(esg_rows), 'validated': len(esg_recs), 'upserted': esg_upserted, **esg_stats}
    }


def main():
    parser = argparse.ArgumentParser(description="Consolidated transfer + ingestion for HappySignals and EPEAT")
    parser.add_argument('--src', default=os.getenv('SRC_CONN'), help='Source connection string (master)')
    parser.add_argument('--dst', default=os.getenv('DST_CONN'), help='Destination connection string (DB_Nexthink)')
    parser.add_argument('--dry-run', action='store_true', help='Do not write to DB')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if not args.src or not args.dst:
        LOG.error('Source and destination connection strings are required (env SRC_CONN/DST_CONN or CLI)')
        return 2

    try:
        result = process_both_from_db(args.src, args.dst, dry_run=args.dry_run)
        LOG.info('Finished processing. Summary: %s', result)
        return 0
    except Exception:
        LOG.exception('Processing failed')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
