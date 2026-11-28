#!/usr/bin/env bash
# One-time load of all India places (LGD) and PIN codes / post offices into your MongoDB.
set -e
cd "$(dirname "$0")/.."
python scripts/run_lgd_import.py
python scripts/import_pincodes.py
python scripts/fill_pin_gaps.py
python scripts/build_main_towns.py
echo "India data loaded."
