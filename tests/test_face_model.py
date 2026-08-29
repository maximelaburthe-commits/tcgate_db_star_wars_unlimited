import json
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class FaceModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards = json.loads((ROOT / "data/cards.json").read_text(encoding="utf-8"))
        cls.printings = json.loads((ROOT / "data/printings.json").read_text(encoding="utf-8"))
        cls.faces = json.loads((ROOT / "data/faces.json").read_text(encoding="utf-8"))

    def test_reference_invariants(self):
        counts = Counter(face["printingId"] for face in self.faces)
        self.assertEqual(len({face["refId"] for face in self.faces}), len(self.faces))
        for printing in self.printings:
            self.assertEqual(counts[printing["id"]], 2 if printing.get("backImageUrl") else 1)

    def test_double_face_canonical_identity(self):
        double_ids = {p["cardId"] for p in self.printings if p.get("backImageUrl")}
        self.assertEqual(len(double_ids), 232)
        card_types = Counter(c["type"] for c in self.cards if c["id"] in double_ids)
        self.assertEqual(card_types, {"Leader": 230, "Base": 2})
        self.assertIn("swu-echo-caverns-base-423862ecfaa0", double_ids)
        self.assertIn("swu-forward-command-post-base-56c5b50e4ce2", double_ids)

    def test_card_number_and_face_counts(self):
        self.assertEqual(sum(bool(p.get("cardNumber")) for p in self.printings), 9185)
        self.assertEqual(Counter(f["side"] for f in self.faces), {"front": 9185, "back": 461})

if __name__ == "__main__":
    unittest.main()
