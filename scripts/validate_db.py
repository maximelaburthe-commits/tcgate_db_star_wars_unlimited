import json
import sys
from collections import Counter
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
cards = json.loads((ROOT / "data/cards.json").read_text(encoding="utf-8"))
printings = json.loads((ROOT / "data/printings.json").read_text(encoding="utf-8"))
faces = json.loads((ROOT / "data/faces.json").read_text(encoding="utf-8"))
coverage = json.loads((ROOT / "data/coverage.json").read_text(encoding="utf-8"))
errors = []
for kind, values in (("card", cards), ("printing", printings), ("face", faces)):
    schema = json.loads((ROOT / "schemas" / f"{kind}.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for index, value in enumerate(values):
        issue = next(validator.iter_errors(value), None)
        if issue:
            errors.append(f"{kind}[{index}] schema: {issue.message}")
            break
card_ids = [x.get("id") for x in cards]
printing_ids = [x.get("id") for x in printings]
ref_ids = [x.get("refId") for x in faces]
known_cards, known_printings = set(card_ids), set(printing_ids)
cards_by_id = {x["id"]: x for x in cards}

def require_unique(label, values):
    if None in values or "" in values:
        errors.append(f"{label} contains an empty ID")
    if len(values) != len(set(values)):
        errors.append(f"duplicate {label}")

require_unique("card ids", card_ids)
require_unique("printing ids", printing_ids)
require_unique("face refIds", ref_ids)
orphan_printings = [p.get("id") for p in printings if p.get("cardId") not in known_cards]
orphan_faces = [f.get("refId") for f in faces if f.get("cardId") not in known_cards or f.get("printingId") not in known_printings]
if orphan_printings: errors.append(f"{len(orphan_printings)} orphan printings")
if orphan_faces: errors.append(f"{len(orphan_faces)} orphan faces")

faces_by_printing = {}
for face in faces:
    faces_by_printing.setdefault(face.get("printingId"), []).append(face)
    if face.get("side") not in {"front", "back"}: errors.append(f"invalid side on {face.get('refId')}")
    if not face.get("imageUrl"): errors.append(f"missing imageUrl on {face.get('refId')}")
    if face.get("refId") != f"{face.get('printingId')}:{face.get('side')}": errors.append(f"unstable refId on {face.get('refId')}")

for printing in printings:
    pid, pf = printing.get("id"), faces_by_printing.get(printing.get("id"), [])
    fronts = [f for f in pf if f.get("side") == "front"]
    backs = [f for f in pf if f.get("side") == "back"]
    if len(fronts) != 1: errors.append(f"{pid} has {len(fronts)} front faces")
    if len(backs) != int(bool(printing.get("backImageUrl"))): errors.append(f"{pid} back face mismatch")
    if fronts and fronts[0].get("imageUrl") != printing.get("frontImageUrl"): errors.append(f"{pid} front image mismatch")
    if backs and backs[0].get("imageUrl") != printing.get("backImageUrl"): errors.append(f"{pid} back image mismatch")
    if not printing.get("cardId"): errors.append(f"{pid} has no cardId")

source_records = int(coverage.get("sourceRecords") or coverage.get("totalCards") or 0)
if source_records and source_records != len(printings): errors.append(f"source record mismatch: {source_records} != {len(printings)}")
source_card_numbers = int(coverage.get("sourceCardNumberCoverage") or 0)
number_coverage = sum(1 for p in printings if p.get("cardNumber") not in (None, ""))
if source_card_numbers and number_coverage != source_card_numbers: errors.append(f"cardNumber coverage mismatch: {source_card_numbers} != {number_coverage}")

printing_double = sum(1 for p in printings if p.get("backImageUrl"))
back_faces = sum(1 for f in faces if f.get("side") == "back")
card_double_ids = {p["cardId"] for p in printings if p.get("backImageUrl")}
for cid in card_double_ids:
    if cards_by_id[cid].get("doubleSided") is not True: errors.append(f"double-sided printing linked to non-double-sided card {cid}")
for card in cards:
    if bool(card.get("doubleSided")) != (card["id"] in card_double_ids): errors.append(f"doubleSided mismatch on {card['id']}")
if len(faces) != len(printings) + printing_double or back_faces != printing_double: errors.append("face count invariant failed")
if int(coverage.get("normalizedFaces") or len(faces)) != len(faces): errors.append("coverage face count mismatch")
used = Counter(p.get("cardId") for p in printings)
if any(used[cid] == 0 for cid in card_ids): errors.append("gameplay card without printing")

print(f"cards={len(cards)} printings={len(printings)} faces={len(faces)} front={len(faces)-back_faces} back={back_faces} cardNumbers={number_coverage} doubleCardIds={len(card_double_ids)} orphans={len(orphan_printings)+len(orphan_faces)}")
if errors:
    print("FAIL:", "; ".join(errors[:20]))
    sys.exit(1)
print("OK")
