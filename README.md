# Star Wars: Unlimited — TCGate DB

Independent Star Wars: Unlimited database package for TCGate.

The database is rebuilt from the public SWU API full export. Every physical printing remains in `data/printings.json`, while Standard/Foil/Hyperspace/Showcase/reprint records are rolled up into gameplay objects in `data/cards.json`.

## GitHub update

For the private alpha, updates remain user-triggered:

1. Open **Actions**.
2. Select **Build or update TCGate database**.
3. Click **Run workflow**.
4. The workflow downloads the full source, validates the normalized database, rebuilds the runtime/Vision index, and commits the generated files when they changed.

No source change is published unless the workflow is manually run.

## Local build

```bash
python -m pip install -r requirements.txt
python source/sync.py
python scripts/validate_db.py
python scripts/build_runtime.py
```

This repository stores metadata and source image URLs, not copyrighted image binaries.

## 0.2.1 normalization fix

Version 0.2.0 could leave each API record as its own gameplay card when upstream parent links did not resolve. 0.2.1 groups from both upstream variant/reprint relations and an exact gameplay-mechanics fingerprint, and the validator now refuses a build where non-standard printings exist but nothing was rolled up.
