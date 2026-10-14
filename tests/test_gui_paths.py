import os
import unittest
from pathlib import Path
from unittest.mock import patch

from src.hn_ano_tool.gui import application_directory


class ApplicationDirectoryTests(unittest.TestCase):
    def test_source_mode_uses_project_root(self):
        expected = Path(__file__).resolve().parents[1]
        self.assertEqual(
            os.path.normcase(application_directory()),
            os.path.normcase(str(expected)),
        )

    def test_frozen_mode_uses_executable_directory(self):
        executable = r"C:\Tools\HealthNoord\HealthNoordAnonymizer.exe"
        with patch("src.hn_ano_tool.gui.sys.frozen", True, create=True), patch(
            "src.hn_ano_tool.gui.sys.executable", executable
        ):
            self.assertEqual(
                os.path.normcase(application_directory()),
                os.path.normcase(os.path.dirname(executable)),
            )


if __name__ == "__main__":
    unittest.main()