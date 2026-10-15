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

    def test_double_surname_with_spaced_hyphen_stays_one_name(self):
        text = "Mevr. van den Broek - Zoon belde over haar zoon. Broek kwam niet."
        result = anonymize(text, patients="van den Broek - Zoon\n")
        self.assertEqual(result, "Mevr. <PERSOON_001> belde over haar zoon. Broek kwam niet.")

    def test_lone_first_or_last_name_needs_a_capital(self):
        text = "Bakker en Anna zijn er. De bakker bracht anna brood. JAN BAKKER ook."
        result = anonymize(text, patients="Anna Bakker\nJan Bakker\n")
        # "Bakker" is shared (ambiguous), "Anna" is a unique first name.
        self.assertEqual(
            result,
            "Bakker en <PERSOON_001> zijn er. De bakker bracht anna brood. <PERSOON_002> ook.",
        )

    def test_single_word_name_needs_a_capital(self):
        text = "Arts belde de arts. Talko en talko."
        result = anonymize(text, patients="Arts\ntalko\n")
        self.assertEqual(result, "<PERSOON_001> belde de arts. <PERSOON_002> en talko.")

    def test_surname_with_tussenvoegsel_needs_a_capital_in_the_surname(self):
        text = "Mw. de Goede zegt: de goede zorg. De heer kwam."
        result = anonymize(text, patients="de Goede\nHeer\n")
        self.assertEqual(result, "Mw. <PERSOON_001> zegt: de goede zorg. De heer kwam.")

    def test_existing_codes_are_never_changed(self):
        text = "[PERSOON-1] sprak Persoon in [LOCATIE-2] op [DATUM-3]."
        result = anonymize(text, patients="Persoon\nDatum\n", locations="Locatie\nPersoon\n")
        self.assertEqual(result, "[PERSOON-1] sprak <PERSOON_001> in [LOCATIE-2] op [DATUM-3].")

    def test_common_word_name_is_skipped_at_sentence_start_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "namen.txt"
            path.write_text("Linker\nAnders\nLaverman\n", encoding="utf-8")
            patterns = build_extra_patterns(extra_names_paths={"patient": str(path)})
        patterns["persoon"].set_common_words(lambda word: word == "anders")

        text = (
            "Linker been gezwollen. Anders gaat het goed.\n"
            "- Linker arm pijnlijk; [DATUM-1] Anders belde.\n"
            "Laverman kwam. Gesprek met mevr. Anders en dhr. Linker."
        )
        result = vervang_gemiste_namen_multi_any(text, patterns, ExtraNamesContext())
        self.assertEqual(
            result,
            "Linker been gezwollen. Anders gaat het goed.\n"
            "- Linker arm pijnlijk; [DATUM-1] <PERSOON_001> belde.\n"
            "<PERSOON_002> kwam. Gesprek met mevr. <PERSOON_001> en dhr. <PERSOON_003>.",
        )

    def test_full_name_still_matches_in_lowercase(self):
        result = anonymize("gesprek met anna bakker", patients="Anna Bakker\n")
        self.assertEqual(result, "gesprek met <PERSOON_001>")

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
