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


if __name__ == "__main__":
    unittest.main()