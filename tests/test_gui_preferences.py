import json
import os
import tempfile
import unittest
from unittest.mock import patch

from src.hn_ano_tool.gui.preferences import load_preferences, preferences_path, save_preferences


class PreferencesTests(unittest.TestCase):
    def test_round_trip_persists_filter_choices_only(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"LOCALAPPDATA": directory}):
                save_preferences({"bsn", "persoon"})
                saved_data = json.loads(preferences_path().read_text(encoding="utf-8"))
                loaded = load_preferences()

        self.assertEqual(saved_data["disabled_groups"], ["bsn", "persoon"])
        self.assertEqual(loaded["disabled_groups"], ["bsn", "persoon"])
        self.assertNotIn("whitelist_path", saved_data)
        self.assertNotIn("input_file", saved_data)
        self.assertNotIn("output_dir", saved_data)
        self.assertNotIn("log_dir", saved_data)

    def test_legacy_whitelist_path_is_ignored_and_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"LOCALAPPDATA": directory}):
                path = preferences_path()
                path.parent.mkdir(parents=True)
                path.write_text(
                    json.dumps(
                        {
                            "disabled_groups": ["dates"],
                            "whitelist_path": r"C:\old\whitelist.txt",
                        }
                    ),
                    encoding="utf-8",
                )

                loaded = load_preferences()
                migrated_data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(loaded, {"disabled_groups": ["dates"]})
        self.assertNotIn("whitelist_path", migrated_data)

    def test_missing_or_invalid_preferences_return_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"LOCALAPPDATA": directory}):
                self.assertEqual(load_preferences(), {})
                path = preferences_path()
                path.parent.mkdir(parents=True)
                path.write_text("not-json", encoding="utf-8")
                self.assertEqual(load_preferences(), {})


if __name__ == "__main__":
    unittest.main()