import hashlib
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
URL = "https://api.swuapi.com/export/all"


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def val(obj, *keys):
    for key in keys:
        if isinstance(obj, dict) and key in obj and obj[key] is not None:
            return obj[key]
    return None


def normalized(value):
    if isinstance(value, list):
        return sorted(normalized(v) for v in value)
    if isinstance(value, dict):
        return {k: normalized(value[k]) for k in sorted(value)}
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def identity_payload_v1(card):
    """Historical v0.2 gameplay payload. Keep byte-compatible to preserve card IDs."""
    aliases = {
        "name": ("name",),
        "subtitle": ("subtitle",),
        "type": ("type",),
        "type2": ("type2", "type_2"),
        "cost": ("cost",),
        "power": ("power",),
        "hp": ("hp",),
        "upgradePower": ("upgradePower", "upgrade_power"),
        "upgradeHp": ("upgradeHp", "upgrade_hp"),
        "arena": ("arena",),
        "aspects": ("aspects",),
        "aspectDuplicates": ("aspectDuplicates", "aspect_duplicates"),
        "traits": ("traits",),
        "keywords": ("keywords",),
        "text": ("text",),
        "deployBox": ("deployBox", "deploy_box"),
        "epicAction": ("epicAction", "epic_action"),
        "rules": ("rules",),
        "isUnique": ("isUnique", "is_unique"),
        "isLeader": ("isLeader", "is_leader"),
        "isBase": ("isBase", "is_base"),
    }
    return {name: normalized(val(card, *keys)) for name, keys in aliases.items()}


def mechanics_payload(card):
    """Gameplay identity used for grouping, including both sides of physical cards."""
    payload = identity_payload_v1(card)
    payload.update(
        {
            "doubleSided": normalized(val(card, "doubleSided", "double_sided")),
            "frontText": normalized(val(card, "frontText", "front_text")),
            "backText": normalized(val(card, "backText", "back_text")),
        }
    )
    return payload


def mechanics_signature(card):
    raw = json.dumps(mechanics_payload(card), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def identifier_tokens(card):
    tokens = set()
    for keys in (
        ("uuid",),
        ("externalId", "external_id"),
        ("externalUid", "external_uid"),
        ("strapiId", "strapi_id"),
        ("id",),
    ):
        value = val(card, *keys)
        if value not in (None, ""):
            tokens.add(str(value))
    return tokens


def relation_refs(card):
    refs = []
    for keys in (("variantOf", "variant_of"), ("reprintOf", "reprint_of")):
        value = val(card, *keys)
        if value in (None, "", 0):
            continue
        if isinstance(value, dict):
            ids = identifier_tokens(value)
            refs.extend(ids or [str(value)])
        elif isinstance(value, list):
            refs.extend(str(v) for v in value if v not in (None, "", 0))
        else:
            refs.append(str(value))
    return refs


class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def representative(rows):
    def score(card):
        variant = str(val(card, "variantType", "variant_type") or "").lower()
        no_parent = not relation_refs(card)
        standard = variant == "standard"
        has_image = bool(val(card, "frontImageUrl", "front_image_url"))
        return (standard and no_parent, standard, no_parent, has_image)

    return max(rows, key=score)


parser = argparse.ArgumentParser()
parser.add_argument("--source-file", type=Path, help="Read a versioned/source snapshot instead of the live API")
args = parser.parse_args()

if args.source_file:
    payload = json.loads(args.source_file.read_text(encoding="utf-8"))
else:
    response = requests.get(URL, timeout=120)
    response.raise_for_status()
    payload = response.json()
raw = payload.get("cards", [])
sets = payload.get("sets", [])
if not raw:
    raise RuntimeError("SWU API export returned no cards; refusing to overwrite the database")

uf = UnionFind(len(raw))
lookup = {}
for index, card in enumerate(raw):
    for token in identifier_tokens(card):
        lookup.setdefault(token, index)

resolved_relations = 0
unresolved_relations = []
for index, card in enumerate(raw):
    for ref in relation_refs(card):
        target = lookup.get(ref)
        if target is None:
            unresolved_relations.append({"sourceIndex": index, "ref": ref})
        else:
            uf.union(index, target)
            resolved_relations += 1

# Safety fallback: variant/reprint links are upstream strapi IDs and have changed
# representation before. Exact gameplay mechanics are therefore also unioned so
# Standard/Foil/Hyperspace/Showcase prints cannot silently become separate cards.
by_mechanics = {}
for index, card in enumerate(raw):
    sig = mechanics_signature(card)
    if sig in by_mechanics:
        uf.union(index, by_mechanics[sig])
    else:
        by_mechanics[sig] = index

groups = defaultdict(list)
for index, card in enumerate(raw):
    groups[uf.find(index)].append(card)

cards = []
card_id_by_group = {}
used_card_ids = set()
for root_index, rows in groups.items():
    rep = representative(rows)
    mechanics = mechanics_payload(rep)
    # v0.3 grouping sees both faces, while IDs deliberately retain the v0.2 seed.
    identity_seed = json.dumps(identity_payload_v1(rep), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    label = slug("-".join(str(x or "") for x in (mechanics.get("name"), mechanics.get("subtitle"), mechanics.get("type"))))[:72]
    digest = hashlib.sha1(identity_seed.encode("utf-8")).hexdigest()[:12]
    cid = f"swu-{label}-{digest}" if label else f"swu-{digest}"
    # Extremely defensive collision guard.
    if cid in used_card_ids:
        cid = f"{cid}-{hashlib.sha1(str(root_index).encode()).hexdigest()[:6]}"
    used_card_ids.add(cid)
    card_id_by_group[root_index] = cid
    card = {"id": cid, **mechanics}
    card["printingCount"] = len(rows)
    cards.append(card)

printings = []
faces = []
variant_counter = Counter()
for index, card in enumerate(raw):
    group = uf.find(index)
    cid = card_id_by_group[group]
    source_id = str(val(card, "uuid", "externalId", "external_id", "externalUid", "external_uid", "id"))
    if source_id in ("None", ""):
        source_id = hashlib.sha1(json.dumps(card, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    set_value = val(card, "setCode", "set_code", "set")
    if isinstance(set_value, dict):
        set_value = val(set_value, "code", "name")
    variant = val(card, "variantType", "variant_type") or "Standard"
    variant_counter[str(variant)] += 1
    printing_id = "swup-" + slug(source_id)
    front_image = val(card, "frontImageUrl", "front_image_url")
    back_image = val(card, "backImageUrl", "back_image_url")
    printings.append(
        {
            "id": printing_id,
            "cardId": cid,
            "sourceId": source_id,
            "set": set_value,
            "cardNumber": val(card, "cardNumber", "card_number"),
            "serialCode": val(card, "serialCode", "serial_code"),
            "variant": variant,
            "rarity": val(card, "rarity"),
            "artist": val(card, "artist"),
            "frontImageUrl": front_image,
            "backImageUrl": back_image,
        }
    )
    if front_image:
        faces.append({"refId": f"{printing_id}:front", "cardId": cid, "printingId": printing_id, "side": "front", "imageUrl": front_image})
    if back_image:
        faces.append({"refId": f"{printing_id}:back", "cardId": cid, "printingId": printing_id, "side": "back", "imageUrl": back_image})

cards.sort(key=lambda x: (str(x.get("name") or ""), str(x.get("subtitle") or ""), x["id"]))
printings.sort(key=lambda x: (str(x.get("set") or ""), x["id"]))
faces.sort(key=lambda x: (x["printingId"], x["side"]))

(ROOT / "data/cards.json").write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
(ROOT / "data/printings.json").write_text(json.dumps(printings, ensure_ascii=False, indent=2), encoding="utf-8")
(ROOT / "data/faces.json").write_text(json.dumps(faces, ensure_ascii=False, indent=2), encoding="utf-8")
(ROOT / "data/sets.json").write_text(json.dumps(sets, ensure_ascii=False, indent=2), encoding="utf-8")

meta = dict(payload.get("meta", {}))
meta.update(
    {
        "sourceRecords": len(raw),
        "normalizedGameplayCards": len(cards),
        "normalizedPrintings": len(printings),
        "sourceSets": len(sets),
        "resolvedParentRelations": resolved_relations,
        "unresolvedParentRelations": len(unresolved_relations),
        "variantTypes": dict(sorted(variant_counter.items())),
        "grouping": "parent relations plus exact gameplay-mechanics fingerprint",
        "normalizationVersion": "swu-normalization-v2",
        "identityModelVersion": "swu-gameplay-fingerprint-v1",
        "faceModelVersion": "swu-face-v1",
        "normalizedFaces": len(faces),
        "sourceCardNumberCoverage": sum(1 for card in raw if val(card, "cardNumber", "card_number") not in (None, "")),
        "doubleSidedPrintings": sum(1 for card in raw if bool(val(card, "doubleSided", "double_sided"))),
        "frontFaces": sum(1 for card in raw if val(card, "frontImageUrl", "front_image_url")),
        "backFaces": sum(1 for card in raw if val(card, "backImageUrl", "back_image_url")),
    }
)
(ROOT / "data/coverage.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(meta, ensure_ascii=False, indent=2))
