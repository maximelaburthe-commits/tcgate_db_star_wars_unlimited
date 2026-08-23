import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cards = json.loads((ROOT / "data/cards.json").read_text(encoding="utf-8"))
printings = json.loads((ROOT / "data/printings.json").read_text(encoding="utf-8"))
coverage = json.loads((ROOT / "data/coverage.json").read_text(encoding="utf-8"))

errors = []
warnings = []
card_ids = [x["id"] for x in cards]
printing_ids = [x["id"] for x in printings]

if not cards:
    errors.append("no gameplay cards generated")
if not printings:
    errors.append("no printings generated")
if len(card_ids) != len(set(card_ids)):
    errors.append("duplicate card ids")
if len(printing_ids) != len(set(printing_ids)):
    errors.append("duplicate printing ids")

known = set(card_ids)
orphans = [p["id"] for p in printings if p.get("cardId") not in known]
if orphans:
    errors.append(f"{len(orphans)} orphan printings")

used = Counter(p.get("cardId") for p in printings)
without_printing = [cid for cid in card_ids if used[cid] == 0]
if without_printing:
    errors.append(f"{len(without_printing)} gameplay cards without printings")

source_records = coverage.get("sourceRecords") or coverage.get("totalCards")
if source_records is not None and int(source_records) != len(printings):
    errors.append(f"source record mismatch: coverage={source_records}, printings={len(printings)}")

variant_types = coverage.get("variantTypes") or {}
nonstandard = sum(v for k, v in variant_types.items() if str(k).lower() != "standard")
if nonstandard > 0 and len(cards) >= len(printings):
    errors.append("variant normalization failed: non-standard prints exist but no printings were grouped")

if len(cards) > len(printings):
    errors.append("more gameplay cards than printings")

unresolved = int(coverage.get("unresolvedParentRelations") or 0)
if unresolved:
    warnings.append(
        f"{unresolved} upstream parent relation(s) could not be resolved by source ID; "
        "exact gameplay fingerprint fallback was used"
    )

missing_front = sum(1 for p in printings if not p.get("frontImageUrl"))
print(
    f"cards={len(cards)} printings={len(printings)} orphans={len(orphans)} "
    f"nonstandard={nonstandard} missingFrontImages={missing_front} unresolvedRelations={unresolved}"
)
for warning in warnings:
    print("WARN:", warning)
if errors:
    print("FAIL:", "; ".join(errors))
    sys.exit(1)
print("OK")
