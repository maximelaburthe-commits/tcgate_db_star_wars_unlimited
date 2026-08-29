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
# Star Wars: Unlimited database

## Identity layers

The database separates a canonical `card`, a physical `printing`, and each physical `face`. A face is identified by `refId`, retains its `cardId` and `printingId`, and is side-specific (`front` or `back`). Leader and landscape Base backs never create a second canonical card.

Checkpoint 3B adds two conservative visual layers:

- a **visual family** groups faces of one `cardId + side` when reproducible image evidence indicates the same visual identity;
- a **recognition group** maps that family to one or more candidate physical printings.

`shared` means several printings are visually indistinguishable with current evidence. `exact_candidate` means a family currently contains one printing, but it is not an exact recognition guarantee. `exact_robust` is deliberately forbidden until checkpoint 3C runs the actual matcher descriptors and physical-card tests. `unknown` records unavailable or insufficient image evidence.

`runtime/canonical-vision-index.json` is the future Stage 1 reference set for recognizing `cardId + side`. `runtime/printing-recognition-index.json` then returns candidate printings without arbitrary selection. The development profile is `swu-v1-canonical-dev`.

## Reproducible visual audit

Install `requirements.txt`, then run:

```text
python scripts/audit_visuals.py
python scripts/build_recognition.py
python scripts/validate_db.py
python -m unittest discover -s tests -v
```

The audit streams remote images, records SHA-256, dimensions and a deterministic 64-bit dHash, and does not store source PNG files. Its resumable URL cache lives under `.cache/swu-vision-audit/` and is gitignored. dHash is grouping evidence only; it is not a TCGate Vision descriptor.
