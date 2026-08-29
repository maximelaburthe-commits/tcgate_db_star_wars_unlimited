"""Print deterministic checkpoint 3B statistics and complex physical-test cases."""
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
load = lambda path: json.loads((ROOT / path).read_text(encoding="utf-8"))


def percentile(values, fraction):
    return sorted(values)[math.ceil(len(values) * fraction) - 1]


def main():
    cards, printings, faces = load("data/cards.json"), load("data/printings.json"), load("data/faces.json")
    fingerprints, families, groups = load("data/visual-fingerprints.json"), load("data/visual-families.json"), load("data/recognition-groups.json")
    canonical = load("runtime/canonical-vision-index.json")
    card_by_id = {x["id"]: x for x in cards}; printing_by_id = {x["id"]: x for x in printings}
    group_by_family = {x["visualFamilyId"]: x for x in groups}
    class_counts = Counter(x["classification"] for x in groups)
    side_counts = Counter(x["side"] for x in canonical)
    family_counts = Counter(x["cardId"] for x in families)
    candidate_counts = [len(x["candidatePrintingIds"]) for x in groups]
    sha_counts = Counter(x["imageSha256"] for x in fingerprints if x.get("imageSha256"))
    url_counts = Counter(x["imageUrl"] for x in fingerprints)
    print(f"faces={len(faces)} imageSuccess={sum(bool(x.get('imageSha256')) for x in fingerprints)} imageFailed={sum(not x.get('imageSha256') for x in fingerprints)}")
    print(f"duplicateShaRefs={sum(n for n in sha_counts.values() if n > 1)} duplicateUrlRefs={sum(n for n in url_counts.values() if n > 1)}")
    print(f"families={len(families)} groups={len(groups)} shared={class_counts['shared']} exact_candidate={class_counts['exact_candidate']} unknown={class_counts['unknown']}")
    print(f"stage1={len(canonical)} front={side_counts['front']} back={side_counts['back']}")
    family_values = list(family_counts.values())
    print(f"familiesPerCard mean={statistics.mean(family_values):.6f} median={statistics.median(family_values):g} p95={percentile(family_values, .95)} max={max(family_values)}")
    print(f"candidatesPerGroup mean={statistics.mean(candidate_counts):.6f} median={statistics.median(candidate_counts):g} p95={percentile(candidate_counts, .95)} max={max(candidate_counts)}")
    by_card_side = defaultdict(list)
    for family in families: by_card_side[(family["cardId"], family["side"])].append(family)
    ranked = []
    for (card_id, side), items in by_card_side.items():
        variants = sorted({printing_by_id[pid].get("variant") for item in items for pid in item["printingIds"]})
        item_groups = [group_by_family[item["visualFamilyId"]] for item in items]
        printing_ids = sorted({pid for group in item_groups for pid in group["candidatePrintingIds"]})
        score = len(printing_ids) * 4 + len(items) * 3 + len(variants) * 2 + (8 if side == "back" else 0) + sum(g["classification"] == "unknown" for g in item_groups) * 10
        reasons = [f"{len(printing_ids)} printings", f"{len(items)} visual families", f"{len(variants)} variants"]
        if side == "back": reasons.append("double-face")
        if any(g["classification"] == "unknown" for g in item_groups): reasons.append("unknown evidence")
        card = card_by_id[card_id]
        ranked.append((score, {"cardName": " — ".join(x for x in (card.get("name"), card.get("subtitle")) if x), "cardId": card_id, "side": side, "visualFamilyIds": [x["visualFamilyId"] for x in items], "recognitionGroupIds": [x["recognitionGroupId"] for x in item_groups], "printingIds": printing_ids, "variantTypes": variants, "reason": ", ".join(reasons)}))
    top = [value for _, value in sorted(ranked, key=lambda x: (-x[0], x[1]["cardId"], x[1]["side"]))[:30]]
    print("TOP30_NAMES=" + " | ".join(f"{x['cardName']} [{x['side']}]" for x in top))
    print("TOP30_JSON=" + json.dumps(top, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
