import tempfile
import unittest
from pathlib import Path

from src.hn_ano_tool.engine.extra_lists import build_extra_patterns
from src.hn_ano_tool.engine.utils import ExtraNamesContext, vervang_gemiste_namen_multi_any


def anonymize(text: str, patients: str = "", locations: str = "") -> str:
    with tempfile.TemporaryDirectory() as directory:
        paths = {}
        if patients:
            paths["patient"] = str(Path(directory) / "patienten.txt")
            Path(paths["patient"]).write_text(patients, encoding="utf-8")
        if locations:
            paths["locatie"] = str(Path(directory) / "locaties.txt")
            Path(paths["locatie"]).write_text(locations, encoding="utf-8")
        patterns = build_extra_patterns(extra_names_paths=paths)
    return vervang_gemiste_namen_multi_any(
        text, patterns, ExtraNamesContext(), order=["persoon", "locatie"]
    )


class ExtraListMatchingTests(unittest.TestCase):
    def test_names_ignore_case_spacing_and_line_breaks(self):
        text = "JAN DE VRIES, jan  de vries, Jan de\nVries en jan De Vries."
        self.assertEqual(
            anonymize(text, patients="Jan de Vries\n"),
            "<PERSOON_001>, <PERSOON_001>, <PERSOON_001> en <PERSOON_001>.",
        )

    def test_name_lists_with_different_case_are_one_person(self):
        result = anonymize("Ilse Postma en Postma", patients="ilse postma\nILSE POSTMA\n")
        self.assertEqual(result, "<PERSOON_001> en <PERSOON_001>")

    def test_invisible_characters_in_list_are_ignored(self):
        patients = "talko \n​Ilse⁠ Postma­\n﻿ \n"
        result = anonymize("Talko sprak Ilse Postma.", patients=patients)
        self.assertEqual(result, "<PERSOON_001> sprak <PERSOON_002>.")

    def test_hyphenated_name_matches_with_space(self):
        result = anonymize("mevr. Smit Kramer belde", patients="Anna Smit-Kramer\n")
        self.assertEqual(result, "mevr. <PERSOON_001> belde")

    def test_locations_ignore_case_separators_and_apostrophes(self):
        locations = "Den Haag\n's-Hertogenbosch\nSint-Oedenrode\n"
        text = "DEN  HAAG, ’S HERTOGENBOSCH, 's-hertogenbosch en sint oedenrode"
        self.assertEqual(
            anonymize(text, locations=locations),
            "<LOCATIE_001>, <LOCATIE_002>, <LOCATIE_002> en <LOCATIE_003>",
        )

    def test_longest_location_wins_and_words_are_not_split(self):
        result = anonymize("Den Haag, Haag en Haagse bluf", locations="Haag\nDen Haag\n")
        self.assertEqual(result, "<LOCATIE_001>, <LOCATIE_002> en Haagse bluf")


if __name__ == "__main__":
    unittest.main()
