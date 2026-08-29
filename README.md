# TCGate DB — Star Wars: Unlimited

Version `0.3.0-dev.1` introduces an explicit card / printing / face foundation.
It does not yet enable SWU Vision in TCGate or Vision Lab.

## Identity model

- **card** is the canonical gameplay identity. Standard, Foil, Hyperspace and
  promo versions remain one card when gameplay is identical.
- **printing** is one physical release identified from the stable upstream UUID.
  It owns the set, `cardNumber`, serial code, variant, rarity and artist.
- **face** is one visible side. It owns `refId`, `cardId`, `printingId`, `side`
  and `imageUrl`.

Leaders and the two double-sided bases use one card and one printing identity
with distinct front/back face references. A deployed leader is never a second
canonical card.

The runtime Vision index retains legacy `id` and adds `refId`. Recognition
groups, descriptors and exact/shared printing classification belong to later
checkpoints.

## Synchronization

```bash
python source/sync.py
python source/sync.py --source-file path/to/swu-export.json
python scripts/validate_db.py
python scripts/build_runtime.py
python -m unittest discover -s tests
```
