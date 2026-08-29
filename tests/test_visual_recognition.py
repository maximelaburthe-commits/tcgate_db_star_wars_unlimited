import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.audit_visuals import analyze, cache_key, load_cache
from scripts.build_recognition import build, stable_id

ROOT = Path(__file__).resolve().parents[1]


def fp(ref, sha="a" * 64, visual="0" * 16):
    return {"refId": ref, "imageSha256": sha, "visualHash": visual, "analysisVersion": 1}


class RecognitionUnitTests(unittest.TestCase):
    def fixture(self, same_url=False, failed=False):
        cards = [{"id": "c1"}]
        printings = [
            {"id": "p1", "cardId": "c1", "variant": "Standard"},
            {"id": "p2", "cardId": "c1", "variant": "Standard Foil"},
        ]
        faces = [
            {"refId": "p1:front", "cardId": "c1", "printingId": "p1", "side": "front", "imageUrl": "u1"},
            {"refId": "p2:front", "cardId": "c1", "printingId": "p2", "side": "front", "imageUrl": "u1" if same_url else "u2"},
        ]
        fingerprints = [fp("p1:front"), fp("p2:front", None if failed else "a" * 64)]
        return cards, printings, faces, fingerprints

    def test_identical_sha_and_same_url_create_shared_family(self):
        for values in (self.fixture(), self.fixture(same_url=True, failed=True)):
            families, groups, _, _ = build(*values)
            self.assertEqual(len(families), 1)
            self.assertEqual(groups[0]["classification"], "shared")

    def test_exact_candidate_and_unknown(self):
        values = self.fixture()
        values[1].pop(); values[2].pop(); values[3].pop()
        self.assertEqual(build(*values)[1][0]["classification"], "exact_candidate")
        values[3][0]["imageSha256"] = None
        self.assertEqual(build(*values)[1][0]["classification"], "unknown")

    def test_front_back_and_card_ids_never_mix(self):
        cards, printings, faces, fingerprints = self.fixture()
        faces[1].update(side="back", refId="p2:back", imageUrl="u1")
        fingerprints[1]["refId"] = "p2:back"
        self.assertEqual(len(build(cards, printings, faces, fingerprints)[0]), 2)
        cards.append({"id": "c2"}); printings[1]["cardId"] = "c2"; faces[1]["cardId"] = "c2"; faces[1]["side"] = "front"
        self.assertEqual(len(build(cards, printings, faces, fingerprints)[0]), 2)

    def test_ids_and_build_are_deterministic(self):
        values = self.fixture()
        first = build(*values)
        second = build(*[list(reversed(value)) for value in values])
        self.assertEqual(first, second)
        self.assertEqual(stable_id("swuvf", "c", "front", "r"), stable_id("swuvf", "c", "front", "r"))

    def test_cache_resume_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / f"{cache_key('u')}.json"
            value = {"cacheVersion": 1, "analysisVersion": 1, "url": "u", "httpStatus": 200}
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertEqual(load_cache(path, "u"), value)
            path.write_text("not-json", encoding="utf-8")
            self.assertIsNone(load_cache(path, "u"))

    @patch("scripts.audit_visuals.requests.get")
    def test_http_error_is_cached(self, get):
        response = Mock(status_code=503, ok=False, content=b"")
        response.headers = {"content-type": "text/plain"}; get.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            value = analyze("https://example.invalid/card.png", Path(directory), 1, 0)
            self.assertEqual(value["httpStatus"], 503)
            self.assertEqual(value["error"], "HTTP 503")


class SnapshotRecognitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load = lambda path: json.loads((ROOT / path).read_text(encoding="utf-8"))
        cls.cards = load("data/cards.json"); cls.families = load("data/visual-families.json"); cls.groups = load("data/recognition-groups.json")

    def groups_for(self, name, subtitle=None):
        ids = {card["id"] for card in self.cards if card["name"] == name and (subtitle is None or card.get("subtitle") == subtitle)}
        return [group for group in self.groups if group["cardId"] in ids]

    def test_known_shared_cases(self):
        self.assertTrue(any(x["classification"] == "shared" for x in self.groups_for("Red Three", "Unstoppable")))
        self.assertTrue(any(x["classification"] == "shared" for x in self.groups_for("Battle Droid")))
        self.assertTrue(any(x["classification"] == "shared" for x in self.groups_for("Clone Trooper")))

    def test_double_sided_leaders_and_bases(self):
        for name, subtitle in [("Darth Vader", "Dark Lord of the Sith"), ("Grogu", "Charming Companion"), ("Moff Gideon", "Formidable Commander"), ("The Mandalorian", "Sworn To The Creed"), ("Echo Caverns", None), ("Forward Command Post", None)]:
            sides = {x["side"] for x in self.groups_for(name, subtitle)}
            self.assertEqual(sides, {"front", "back"}, (name, subtitle))

    def test_no_exact_robust(self):
        self.assertNotIn("exact_robust", {x["classification"] for x in self.groups})


if __name__ == "__main__":
    unittest.main()
