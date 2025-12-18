# EPEAT Data Ingestion

This solution ingests EPEAT sustainability data into `ExpNXT.RAW_ESG_METRICS`.

## Components
- `ingest_epeat.py`: Main ingestion script with fuzzy matching logic.
- `sql/usp_upsert_epeat_batch.sql`: Stored procedure for ensuring unique insertions (idempotency).
- `sql/create_esg_load_audit_table.sql`: Audit table DDL.

## Setup

1.  **Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    (Ensure `fuzzywuzzy[speedup]` and `python-Levenshtein` are installed for performance).

2.  **Database**:
    Run the SQL scripts to create the table and stored procedure.
    ```bash
    python apply_schema.py
    ```
    (Alternatively run the SQL files in `sql/` manually).

3.  **Environment**:
    Ensure `.env` contains `EXPNXT_DB_CONN`.

## Usage

### Dry Run
Validate the file and matching logic without writing to DB:
```bash
python ingest_epeat.py --input "Advanced_ProductSummary_2025-12-12T03_12_38.xlsx" --sheet "EPEAT 2.0" --mode dry-run
```

### Full Load
Ingest data:
```bash
python ingest_epeat.py --input "Advanced_ProductSummary_2025-12-12T03_12_38.xlsx" --sheet "EPEAT 2.0" --mode run
```

## Logic
- **Matching**: Attempts to match `Product Name` against existing `ExpNXT.RAW_ESG_METRICS` (or inventory) using exact and fuzzy matching.
- **Deduplication**: Rows are skipped if `device_model` + `epeat_rating` + `material_composition` match existing rows.
- **Audit**: Logs execution stats to `ExpNXT.esg_load_audit`.
