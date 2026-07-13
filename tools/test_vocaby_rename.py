from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
LEGACY_PATTERN = r"wording[-_ ]?daily"


class VocabyRenameTests(unittest.TestCase):
    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
        )

    def test_tracked_paths_use_vocaby(self):
        result = self.git("ls-files")
        self.assertEqual(result.returncode, 0, result.stderr)
        legacy = [
            path
            for path in result.stdout.splitlines()
            if re.search(LEGACY_PATTERN, path, re.IGNORECASE)
        ]
        self.assertEqual(legacy, [])

        for path in (
            "Vocaby.xcodeproj/project.pbxproj",
            "Vocaby.xcodeproj/xcshareddata/xcschemes/Vocaby.xcscheme",
            "Vocaby/App/VocabyApp.swift",
            "Vocaby/Vocaby.entitlements",
            "VocabyTests",
            "VocabyWidget/VocabyWidget.swift",
            "VocabyWidget/VocabyWidget.entitlements",
            ".agents/skills/vocaby-vocabulary-import/SKILL.md",
        ):
            self.assertTrue((ROOT / path).exists(), path)

    def test_tracked_text_uses_vocaby(self):
        result = self.git("grep", "-Il", "-i", "-E", LEGACY_PATTERN, "--", ".")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        self.assertEqual(result.stdout.splitlines(), [])

    def test_xcode_project_references_the_renamed_app_entry_point(self):
        project = (ROOT / "Vocaby.xcodeproj/project.pbxproj").read_text(
            encoding="utf-8"
        )
        self.assertIn("path = VocabyApp.swift;", project)
        self.assertNotIn("Vocaby.swift", project)


if __name__ == "__main__":
    unittest.main()
