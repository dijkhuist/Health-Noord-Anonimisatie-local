import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.hn_ano_tool.engine.core import Anonymizer
from src.hn_ano_tool.engine.extra_lists import (
    build_whitelist_pattern,
    protect_whitelist_terms,
    restore_whitelist_terms,
)


class WhitelistTests(unittest.TestCase):
    def test_protects_full_case_insensitive_phrase_and_restores_original_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "whitelist.txt"
            path.write_text("Gabriele-de Vries syndroom\n", encoding="utf-8")
            pattern = build_whitelist_pattern(str(path))

        original = "Het GABRIELE-de Vries syndroom is erfelijk."
        protected_text, replacements = protect_whitelist_terms(original, pattern)

        self.assertNotIn("GABRIELE", protected_text)
        self.assertTrue(all(not char.isalnum() for token in replacements for char in token))
        self.assertEqual(
            restore_whitelist_terms(protected_text, replacements),
            original,
        )

    def test_does_not_match_term_inside_a_larger_word(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "whitelist.txt"
            path.write_text("de Vries\n", encoding="utf-8")
            pattern = build_whitelist_pattern(str(path))

        text = "Vriesachtig en de Vries"
        protected_text, replacements = protect_whitelist_terms(text, pattern)

        self.assertEqual(len(replacements), 1)
        self.assertEqual(restore_whitelist_terms(protected_text, replacements), text)

    def test_anonymizer_hides_whitelisted_phrase_from_deduce(self):
        class IdentifierDetectingDeduce:
            def __init__(self):
                self.received_text = None

            def deidentify(self, text, enabled=None, disabled=None):
                self.received_text = text
                annotations = []
                for match in re.finditer(r"\w+", text):
                    value = match.group(0)
                    if any(char.isalpha() for char in value) and any(char.isdigit() for char in value):
                        annotations.append(
                            SimpleNamespace(
                                start_char=match.start(),
                                end_char=match.end(),
                                tag="id",
                                text=value,
                            )
                        )
                return SimpleNamespace(annotations=annotations)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "whitelist.txt"
            path.write_text("Gabriele-de Vries syndroom\n", encoding="utf-8")
            deduce = IdentifierDetectingDeduce()
            with patch("src.hn_ano_tool.engine.core.get_deduce", return_value=deduce):
                anonymizer = Anonymizer(whitelist_path=str(path))
            anonymizer.extra_names_patterns = {
                "persoon": re.compile("Gabriele", flags=re.IGNORECASE)
            }

        original = "Gabriele-de Vries syndroom"
        output, _ = anonymizer.anonymize(original)

        self.assertNotIn("Gabriele", deduce.received_text)
        self.assertEqual(output, original)

    def test_term_in_extra_list_is_anonymized_even_when_whitelisted(self):
        class NoOpDeduce:
            def deidentify(self, text, enabled=None, disabled=None):
                return SimpleNamespace(annotations=[])

        with tempfile.TemporaryDirectory() as directory:
            whitelist = Path(directory) / "whitelist.txt"
            whitelist.write_text("Gabriele-de Vries syndroom\nTalko\n", encoding="utf-8")
            patients = Path(directory) / "patienten.txt"
            patients.write_text("talko\n", encoding="utf-8")
            with patch("src.hn_ano_tool.engine.core.get_deduce", return_value=NoOpDeduce()):
                anonymizer = Anonymizer(
                    whitelist_path=str(whitelist),
                    extra_names_paths={"patient": str(patients)},
                )

        output, _ = anonymizer.anonymize("Talko heeft het Gabriele-de Vries syndroom.")

        self.assertEqual(output, "<PERSOON_001> heeft het Gabriele-de Vries syndroom.")

    def test_listed_name_is_replaced_whole_before_deduce_can_split_it(self):
        class SplittingDeduce:
            """Tags only the last word of a surname, as Deduce sometimes does."""

            received_text = ""

            def deidentify(self, text, enabled=None, disabled=None):
                self.received_text = text
                annotations = [
                    SimpleNamespace(start_char=m.start(), end_char=m.end(), tag="persoon", text=m.group(0))
                    for m in re.finditer(r"Berg|Pieters", text)
                ]
                return SimpleNamespace(annotations=annotations)

        with tempfile.TemporaryDirectory() as directory:
            patients = Path(directory) / "patienten.txt"
            patients.write_text("Jan van der Berg-Smit\n", encoding="utf-8")
            deduce = SplittingDeduce()
            with patch("src.hn_ano_tool.engine.core.get_deduce", return_value=deduce):
                anonymizer = Anonymizer(extra_names_paths={"patient": str(patients)})

        output, stats = anonymizer.anonymize("Mevr. Van der Berg-Smit en Jan belden met Pieters.")

        self.assertEqual(output, "Mevr. <PERSOON_001> en <PERSOON_001> belden met [PERSOON-1].")
        self.assertNotIn("Berg", deduce.received_text)  # Deduce never sees the listed name
        self.assertEqual(stats.by_type["extra persoon"], 2)

    def test_postcode_with_capital_mg_is_redacted_but_a_dose_is_not(self):
        class NoOpDeduce:
            def deidentify(self, text, enabled=None, disabled=None):
                return SimpleNamespace(annotations=[])

        with patch("src.hn_ano_tool.engine.core.get_deduce", return_value=NoOpDeduce()):
            anonymizer = Anonymizer()
            without_locations = Anonymizer(disabled={"locations"})

        text = "Postcode 9257MG en 9257 MG; paracetamol 1000 mg, 500MG-tablet."
        output, stats = anonymizer.anonymize(text)

        self.assertEqual(output, "Postcode [LOCATIE-1] en [LOCATIE-2]; paracetamol 1000 mg, 500MG-tablet.")
        self.assertEqual(stats.by_type["locatie"], 2)
        self.assertEqual(without_locations.anonymize(text)[0], text)

    def test_whitelist_wins_for_one_word_name_that_is_an_everyday_word(self):
        class NoOpDeduce:
            lookup_structs = {"whitelist": {"zondag"}}

            def deidentify(self, text, enabled=None, disabled=None):
                return SimpleNamespace(annotations=[])

        with tempfile.TemporaryDirectory() as directory:
            whitelist = Path(directory) / "whitelist.txt"
            whitelist.write_text("Zondag\nLinker\nTalko\n", encoding="utf-8")
            names = Path(directory) / "namen.txt"
            names.write_text("Zondag\nLinker\nTalko\n", encoding="utf-8")
            with patch("src.hn_ano_tool.engine.core.get_deduce", return_value=NoOpDeduce()):
                anonymizer = Anonymizer(
                    whitelist_path=str(whitelist),
                    extra_names_paths={"medewerker": str(names)},
                )

        output, _ = anonymizer.anonymize("Op Zondag kwam Talko, de Linker arm deed pijn.")

        self.assertEqual(output, "Op Zondag kwam <PERSOON_001>, de Linker arm deed pijn.")


if __name__ == "__main__":
    unittest.main()