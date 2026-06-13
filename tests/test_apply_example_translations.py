import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "apply-example-translations.py"


def load_script():
    spec = importlib.util.spec_from_file_location("apply_example_translations", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ApplyExampleTranslationsTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def test_parse_translation_blocks(self):
        text = """No. 1
Danish: Jeg havde en aftale med ham
Source: aftale#600 ex1
Chinese: 我跟他有个约定
English: I had an agreement with him
---

No. 2
Danish: Hun tog kruset
Source: det#3 ex1
Chinese: 她拿起杯子
English: She took the mug
---
"""

        translations = self.script.parse_translation_text(text)

        self.assertEqual(
            translations["Jeg havde en aftale med ham"],
            {"zh": "我跟他有个约定", "en": "I had an agreement with him"},
        )
        self.assertEqual(
            translations["Hun tog kruset"],
            {"zh": "她拿起杯子", "en": "She took the mug"},
        )

    def test_parse_translation_blocks_preserves_placeholder_values(self):
        text = """No. 1
Danish: Og så havde Nino en imponerende samling af våben
Source: våben#425 ex1
Chinese: [待翻译]
English: [待翻译]
---
"""

        translations = self.script.parse_translation_text(text)

        self.assertEqual(
            translations["Og så havde Nino en imponerende samling af våben"],
            {"zh": "[待翻译]", "en": "[待翻译]"},
        )

    def test_parse_translation_blocks_later_duplicate_overwrites_previous_value(self):
        text = """No. 1
Danish: han havde både bil, hus og formue, da de blev gift
Source: har#9 ex1
Chinese: 他们结婚时，他有车有房，还有一笔财产
English: He had a car, a house, and a fortune when they got married
---

No. 1
Danish: han havde både bil, hus og formue, da de blev gift
Source: har#9 ex1
Chinese: [待翻译]
English: [待翻译]
---
"""

        translations = self.script.parse_translation_text(text)

        self.assertEqual(
            translations["han havde både bil, hus og formue, da de blev gift"],
            {"zh": "[待翻译]", "en": "[待翻译]"},
        )

    def test_apply_translations_to_primary_examples(self):
        deck = {
            "total": 2,
            "words": [
                {
                    "id": "aftale",
                    "exampleDa": "Jeg havde en aftale med ham",
                    "examplesDa": ["Jeg havde en aftale med ham"],
                },
                {
                    "id": "mangler",
                    "exampleDa": "Ingen oversættelse",
                    "examplesDa": ["Ingen oversættelse"],
                },
            ],
        }
        translations = {
            "Jeg havde en aftale med ham": {
                "zh": "我跟他有个约定",
                "en": "I had an agreement with him",
            }
        }

        result = self.script.apply_translations(deck, translations)

        self.assertEqual(result.matched, 1)
        self.assertEqual(result.missing, 1)
        self.assertEqual(deck["words"][0]["exampleZh"], "我跟他有个约定")
        self.assertEqual(deck["words"][0]["exampleEn"], "I had an agreement with him")
        self.assertEqual(deck["words"][1]["exampleZh"], "")
        self.assertEqual(deck["words"][1]["exampleEn"], "")

    def test_apply_translations_can_fall_back_to_source_reference(self):
        deck = {
            "total": 1,
            "words": [
                {
                    "id": "de",
                    "word": "de",
                    "rank": 16,
                    "exampleDa": "Han talte med sin far, han talte med sin mor",
                    "examplesDa": ["Han talte med sin far, han talte med sin mor"],
                },
            ],
        }
        translations = {}
        source_translations = {
            "de#16 ex1": {
                "zh": "他同父亲说话，同母亲说话",
                "en": "He spoke with his father and his mother",
            }
        }

        result = self.script.apply_translations(deck, translations, source_translations)

        self.assertEqual(result.matched, 1)
        self.assertEqual(deck["words"][0]["exampleZh"], "他同父亲说话，同母亲说话")
        self.assertEqual(deck["words"][0]["exampleEn"], "He spoke with his father and his mother")

    def test_apply_translation_file_writes_updated_deck(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            deck_path = tmp_path / "deck.json"
            translations_path = tmp_path / "translations.txt"
            deck_path.write_text(
                '{"total": 1, "words": [{"id": "aftale", "exampleDa": "Jeg havde en aftale med ham", "examplesDa": []}]}',
                encoding="utf-8",
            )
            translations_path.write_text(
                "No. 1\nDanish: Jeg havde en aftale med ham\nChinese: 我跟他有个约定\nEnglish: I had an agreement with him\n---\n",
                encoding="utf-8",
            )

            result = self.script.apply_translation_file(deck_path, translations_path)

            self.assertEqual(result.matched, 1)
            self.assertIn('"exampleZh": "我跟他有个约定"', deck_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
