import json
import sys
from collections import Counter
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
cards = json.loads((ROOT / "data/cards.json").read_text(encoding="utf-8"))
printings = json.loads((ROOT / "data/printings.json").read_text(encoding="utf-8"))
faces = json.loads((ROOT / "data/faces.json").read_text(encoding="utf-8"))
families = json.loads((ROOT / "data/visual-families.json").read_text(encoding="utf-8"))
groups = json.loads((ROOT / "data/recognition-groups.json").read_text(encoding="utf-8"))
fingerprints = json.loads((ROOT / "data/visual-fingerprints.json").read_text(encoding="utf-8"))
canonical = json.loads((ROOT / "runtime/canonical-vision-index.json").read_text(encoding="utf-8"))
printing_index = json.loads((ROOT / "runtime/printing-recognition-index.json").read_text(encoding="utf-8"))
coverage = json.loads((ROOT / "data/coverage.json").read_text(encoding="utf-8"))
errors = []
for kind, values in (("card", cards), ("printing", printings), ("face", faces), ("visual-family", families), ("recognition-group", groups)):
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
family_ids = [x.get("visualFamilyId") for x in families]
group_ids = [x.get("recognitionGroupId") for x in groups]
known_cards, known_printings = set(card_ids), set(printing_ids)
cards_by_id = {x["id"]: x for x in cards}
printings_by_id = {x["id"]: x for x in printings}
faces_by_id = {x["refId"]: x for x in faces}
families_by_id = {x["visualFamilyId"]: x for x in families}
groups_by_id = {x["recognitionGroupId"]: x for x in groups}

def require_unique(label, values):
    if None in values or "" in values:
        errors.append(f"{label} contains an empty ID")
    if len(values) != len(set(values)):
        errors.append(f"duplicate {label}")

require_unique("card ids", card_ids)
require_unique("printing ids", printing_ids)
require_unique("face refIds", ref_ids)
require_unique("visual family ids", family_ids)
require_unique("recognition group ids", group_ids)
require_unique("fingerprint refIds", [x.get("refId") for x in fingerprints])
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

family_membership = Counter(ref_id for family in families for ref_id in family.get("refIds", []))
if set(family_membership) != set(ref_ids) or any(count != 1 for count in family_membership.values()): errors.append("each face must belong to exactly one visual family")
covered_printings = set()
for family in families:
    family_faces = [faces_by_id.get(ref_id) for ref_id in family.get("refIds", [])]
    if None in family_faces: errors.append(f"orphan ref in {family.get('visualFamilyId')}"); continue
    pairs = {(face["cardId"], face["side"]) for face in family_faces}
    actual_printings = {face["printingId"] for face in family_faces}
    if pairs != {(family.get("cardId"), family.get("side"))}: errors.append(f"card/side mixing in {family.get('visualFamilyId')}")
    if actual_printings != set(family.get("printingIds", [])): errors.append(f"printing coverage mismatch in {family.get('visualFamilyId')}")
    covered_printings.update(actual_printings)
if covered_printings != known_printings: errors.append("not all printings are covered by visual families")

family_group_counts = Counter(group.get("visualFamilyId") for group in groups)
if set(family_group_counts) != set(family_ids) or any(count != 1 for count in family_group_counts.values()): errors.append("each visual family must have exactly one recognition group")
for group in groups:
    family = families_by_id.get(group.get("visualFamilyId"))
    if not family: errors.append(f"orphan family on {group.get('recognitionGroupId')}"); continue
    if (group.get("cardId"), group.get("side")) != (family["cardId"], family["side"]): errors.append(f"group card/side mismatch on {group.get('recognitionGroupId')}")
    candidates = group.get("candidatePrintingIds", [])
    if not candidates: errors.append(f"empty candidates on {group.get('recognitionGroupId')}")
    if set(candidates) != set(family["printingIds"]): errors.append(f"candidate/family mismatch on {group.get('recognitionGroupId')}")
    if any(printings_by_id.get(pid, {}).get("cardId") != group.get("cardId") for pid in candidates): errors.append(f"cross-card candidate on {group.get('recognitionGroupId')}")
    representative = faces_by_id.get(group.get("representativeRefId"))
    if not representative or group.get("representativeRefId") not in family["refIds"]: errors.append(f"invalid representative on {group.get('recognitionGroupId')}")
    if group.get("classification") == "exact_robust": errors.append("exact_robust is forbidden in checkpoint 3B")

if len(canonical) != len(families): errors.append("canonical reference/family count mismatch")
for ref in canonical:
    face = faces_by_id.get(ref.get("refId")); family = families_by_id.get(ref.get("visualFamilyId")); group = groups_by_id.get(ref.get("recognitionGroupId"))
    if not face or not family or not group: errors.append(f"orphan canonical ref {ref.get('refId')}"); continue
    if ref["refId"] != group["representativeRefId"] or ref["cardId"] != face["cardId"] or ref["side"] != face["side"]: errors.append(f"canonical identity mismatch {ref.get('refId')}")
if {x.get("refId") for x in fingerprints} != set(ref_ids): errors.append("fingerprint coverage mismatch")
if any(x.get("analysisVersion") != 1 for x in fingerprints): errors.append("visual analysis version mismatch")
if printing_index.get("recognitionModelVersion") != "swu-recognition-v1-dev" or printing_index.get("recognitionProfileId") != "swu-v1-canonical-dev": errors.append("recognition index version mismatch")
classification_counts = Counter(x.get("classification") for x in groups)
expected_coverage = {
    "imageAnalysisSuccess": sum(bool(x.get("imageSha256")) for x in fingerprints),
    "imageAnalysisFailure": sum(not x.get("imageSha256") for x in fingerprints),
    "visualFamilies": len(families), "recognitionGroups": len(groups),
    "sharedRecognitionGroups": classification_counts["shared"],
    "exactCandidateRecognitionGroups": classification_counts["exact_candidate"],
    "unknownRecognitionGroups": classification_counts["unknown"],
    "canonicalVisionReferences": len(canonical),
    "canonicalVisionFrontReferences": sum(x.get("side") == "front" for x in canonical),
    "canonicalVisionBackReferences": sum(x.get("side") == "back" for x in canonical),
}
for key, expected in expected_coverage.items():
    if coverage.get(key) != expected: errors.append(f"coverage {key} mismatch: {coverage.get(key)} != {expected}")

print(f"cards={len(cards)} printings={len(printings)} faces={len(faces)} front={len(faces)-back_faces} back={back_faces} families={len(families)} groups={len(groups)} canonicalRefs={len(canonical)} cardNumbers={number_coverage} doubleCardIds={len(card_double_ids)} orphans={len(orphan_printings)+len(orphan_faces)}")
if errors:
    print("FAIL:", "; ".join(errors[:20]))
    sys.exit(1)
print("OK")
