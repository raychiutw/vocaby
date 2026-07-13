from pathlib import Path
import plistlib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AppConfigurationTests(unittest.TestCase):
    def test_main_app_supports_all_ipad_multitasking_orientations(self):
        with (ROOT / "Vocaby/Info.plist").open("rb") as file:
            info = plistlib.load(file)

        self.assertEqual(
            info.get("UISupportedInterfaceOrientations"),
            [
                "UIInterfaceOrientationPortrait",
                "UIInterfaceOrientationPortraitUpsideDown",
                "UIInterfaceOrientationLandscapeLeft",
                "UIInterfaceOrientationLandscapeRight",
            ],
        )


if __name__ == "__main__":
    unittest.main()
