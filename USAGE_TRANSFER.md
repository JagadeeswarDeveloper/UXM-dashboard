# transfer_all.py — Usage

This repository was consolidated to include a single `transfer_all.py` script that:

- Fetches `RAW_HAPPYSIGNALS_SURVEYS` and `RAW_ESG_METRICS` from the source DB (`master`).
- Inserts rows into the destination DB (`DB_Nexthink`).
- Supports `--dry-run` to simulate the transfer without DB writes.

Quick start:

1. Install requirements:
   pip install -r requirements.txt

2. Configure connection strings via environment variables or pass them on the CLI:

   - SRC_CONN: connection string to the source (master) DB
   - DST_CONN: connection string to the destination (DB_Nexthink)

3. Dry run (safe, no writes):

   python transfer_all.py --dry-run --src "<SRC_CONN>" --dst "<DST_CONN>"

4. Real run (will write to destination):

   python transfer_all.py --src "<SRC_CONN>" --dst "<DST_CONN>"

Notes:
- The script intentionally avoids hard-coded credentials and prefers env variables.
- Unit tests exist in `tests/test_transfer_all.py` and the existing test suite covers ingestion logic.
- Running the real transfer requires valid DB access; do this on a machine with secure credentials.
