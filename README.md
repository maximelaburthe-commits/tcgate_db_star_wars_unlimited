# Star Wars: Unlimited — TCGate DB

Public full export of cards and sets; variants/reprints normalized.

## Build

```bash
python -m pip install -r requirements.txt
python source/sync.py
python scripts/validate_db.py
python scripts/build_runtime.py
```

The private-alpha publication step remains manual: review the generated files, then commit them to the dedicated GitHub repository.

This package stores card metadata and image URLs, not copyrighted image binaries.
