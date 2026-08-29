"""Build conservative visual families and SWU recognition indexes."""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "swu-v1-canonical-dev"
MODEL = "swu-recognition-v1-dev"


def stable_id(prefix, *parts):
    payload = "\x1f".join(str(x) for x in parts)
    return f"{prefix}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def hamming(left, right):
    return (int(left, 16) ^ int(right, 16)).bit_count()


def variant_family(value):
    value = re.sub(r"\s+foil$", "", (value or "").strip(), flags=re.I)
    return value.casefold()


class UnionFind:
    def __init__(self, values):
        self.parent = {value: value for value in values}
    def find(self, value):
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value
    def union(self, left, right):
        left, right = self.find(left), self.find(right)
        if left != right:
            self.parent[max(left, right)] = min(left, right)


def build(cards, printings, faces, fingerprints):
    printing_by_id = {item["id"]: item for item in printings}
    fp_by_ref = {item["refId"]: item for item in fingerprints}
    buckets = defaultdict(list)
    for face in faces:
        buckets[(face["cardId"], face["side"])].append(face)
    families = []
    groups = []
    canonical = []
    for (card_id, side), members in sorted(buckets.items()):
        members.sort(key=lambda item: item["refId"])
        union = UnionFind([item["refId"] for item in members])
        for index, left in enumerate(members):
            lfp = fp_by_ref[left["refId"]]
            lp = printing_by_id[left["printingId"]]
            for right in members[index + 1:]:
                rfp = fp_by_ref[right["refId"]]
                rp = printing_by_id[right["printingId"]]
                same_sha = lfp.get("imageSha256") and lfp["imageSha256"] == rfp.get("imageSha256")
                same_url = left["imageUrl"] == right["imageUrl"]
                close = lfp.get("visualHash") and rfp.get("visualHash") and hamming(lfp["visualHash"], rfp["visualHash"]) <= 2
                coherent = variant_family(lp.get("variant")) == variant_family(rp.get("variant"))
                if same_sha or same_url or (close and coherent):
                    union.union(left["refId"], right["refId"])
        components = defaultdict(list)
        for member in members:
            components[union.find(member["refId"])].append(member)
        for component in sorted(components.values(), key=lambda value: min(x["refId"] for x in value)):
            ref_ids = sorted(x["refId"] for x in component)
            printing_ids = sorted({x["printingId"] for x in component})
            family_id = stable_id("swuvf", card_id, side, *ref_ids)
            group_id = stable_id("swurg", family_id)
            successful = all(fp_by_ref[x].get("imageSha256") for x in ref_ids)
            classification = "shared" if len(printing_ids) > 1 else ("exact_candidate" if successful else "unknown")
            reason = "multiple printings share one visual family" if classification == "shared" else ("single visually distinct printing candidate" if classification == "exact_candidate" else "image evidence unavailable")
            representative = min(ref_ids, key=lambda ref: (not bool(fp_by_ref[ref].get("imageSha256")), ref))
            evidence = {
                "imageSha256s": sorted({fp_by_ref[x].get("imageSha256") for x in ref_ids if fp_by_ref[x].get("imageSha256")}),
                "imageUrls": sorted({next(f["imageUrl"] for f in component if f["refId"] == x) for x in ref_ids}),
                "visualHashes": sorted({fp_by_ref[x].get("visualHash") for x in ref_ids if fp_by_ref[x].get("visualHash")}),
            }
            if len(ref_ids) == 1:
                relation = "UNKNOWN"
            elif len(evidence["imageSha256s"]) == 1 or len(evidence["imageUrls"]) == 1:
                relation = "VISUALLY_IDENTICAL"
            else:
                relation = "LIKELY_SAME_ARTWORK"
            families.append({"visualFamilyId": family_id, "cardId": card_id, "side": side, "refIds": ref_ids, "printingIds": printing_ids, "relationClassification": relation})
            groups.append({"recognitionGroupId": group_id, "cardId": card_id, "side": side, "visualFamilyId": family_id, "printingIds": printing_ids, "candidatePrintingIds": printing_ids, "classification": classification, "reason": reason, "evidence": evidence, "representativeRefId": representative})
            rep_face = next(face for face in component if face["refId"] == representative)
            canonical.append({"refId": representative, "cardId": card_id, "side": side, "visualFamilyId": family_id, "recognitionGroupId": group_id, "representativePrintingId": rep_face["printingId"], "imageUrl": rep_face["imageUrl"], "recognitionProfileId": PROFILE})
    families.sort(key=lambda item: item["visualFamilyId"])
    groups.sort(key=lambda item: item["recognitionGroupId"])
    canonical.sort(key=lambda item: item["refId"])
    nested = []
    by_card = defaultdict(lambda: defaultdict(list))
    for group in groups:
        by_card[group["cardId"]][group["side"]].append({
            "recognitionGroupId": group["recognitionGroupId"], "visualFamilyId": group["visualFamilyId"],
            "printingId": group["candidatePrintingIds"][0] if group["classification"] == "exact_candidate" else None,
            "candidatePrintingIds": group["candidatePrintingIds"], "classification": group["classification"],
        })
    for card_id in sorted(by_card):
        nested.append({"cardId": card_id, "sides": [{"side": side, "recognitionGroups": sorted(items, key=lambda x: x["recognitionGroupId"])} for side, items in sorted(by_card[card_id].items())]})
    return families, groups, canonical, {"recognitionModelVersion": MODEL, "recognitionProfileId": PROFILE, "cards": nested}


def write(path, value, compact=False):
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":") if compact else None, indent=None if compact else 2)
    path.write_text(text + ("" if compact else "\n"), encoding="utf-8")


def main():
    load = lambda path: json.loads((ROOT / path).read_text(encoding="utf-8"))
    values = build(load("data/cards.json"), load("data/printings.json"), load("data/faces.json"), load("data/visual-fingerprints.json"))
    write(ROOT / "data/visual-families.json", values[0])
    write(ROOT / "data/recognition-groups.json", values[1])
    write(ROOT / "runtime/canonical-vision-index.json", values[2], compact=True)
    write(ROOT / "runtime/printing-recognition-index.json", values[3], compact=True)
    print(f"families={len(values[0])} groups={len(values[1])} canonicalRefs={len(values[2])}")


if __name__ == "__main__":
    main()
