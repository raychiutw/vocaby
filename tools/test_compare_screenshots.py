from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

try:
    from PIL import Image
except ImportError:  # CI runner 不一定有 Pillow
    Image = None


SCRIPT = Path(__file__).resolve().parent / "compare_screenshots.py"


def _png(path: Path, color):
    Image.new("RGB", (8, 8), color).save(path)


def _run(baseline: Path, current: Path, report: Path, *extra):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(baseline), str(current), str(report), *extra],
        capture_output=True,
        text=True,
    )


@unittest.skipIf(Image is None, "Pillow is not installed")
class CompareScreenshotsTests(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.baseline, self.current, self.report = tmp / "b", tmp / "c", tmp / "r"
        self.baseline.mkdir()
        self.current.mkdir()

    def test_identical_images_pass(self):
        _png(self.baseline / "today-light.png", (255, 255, 255))
        _png(self.current / "today-light.png", (255, 255, 255))
        result = _run(self.baseline, self.current, self.report)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changed_image_fails_and_writes_side_by_side_report(self):
        _png(self.baseline / "today-dark.png", (0, 0, 0))
        _png(self.current / "today-dark.png", (0, 0, 20))
        result = _run(self.baseline, self.current, self.report)
        self.assertEqual(result.returncode, 1)
        self.assertIn("today-dark.png", result.stdout)
        report = Image.open(self.report / "today-dark.png")
        self.assertEqual(report.size, (24, 8))  # 基準 | 目前 | 差異

    def test_missing_and_new_screens_fail(self):
        _png(self.baseline / "gone-light.png", (0, 0, 0))
        _png(self.current / "new-light.png", (0, 0, 0))
        result = _run(self.baseline, self.current, self.report)
        self.assertEqual(result.returncode, 1)
        self.assertIn("gone-light.png", result.stdout)
        self.assertIn("new-light.png", result.stdout)

    def test_update_replaces_baseline(self):
        _png(self.baseline / "a-light.png", (0, 0, 0))
        _png(self.current / "a-light.png", (9, 9, 9))
        self.assertEqual(_run(self.baseline, self.current, self.report, "--update").returncode, 0)
        self.assertEqual(_run(self.baseline, self.current, self.report).returncode, 0)

    def test_update_with_empty_current_keeps_baseline(self):
        _png(self.baseline / "a-light.png", (0, 0, 0))
        result = _run(self.baseline, self.current, self.report, "--update")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.baseline / "a-light.png").exists())

    def test_size_mismatch_is_called_out(self):
        _png(self.baseline / "a-light.png", (0, 0, 0))
        Image.new("RGB", (4, 4), (0, 0, 0)).save(self.current / "a-light.png")
        result = _run(self.baseline, self.current, self.report)
        self.assertEqual(result.returncode, 1)
        self.assertIn("尺寸", result.stdout)

    def test_ignored_screens_are_not_compared(self):
        _png(self.baseline / "home-light.png", (0, 0, 0))
        _png(self.current / "home-light.png", (0, 0, 0))
        _png(self.current / "progress-light.png", (5, 5, 5))  # 基準沒有,但被忽略
        result = _run(self.baseline, self.current, self.report, "--ignore", "progress-*")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("progress-light.png", result.stdout)

    def test_update_does_not_copy_ignored_screens(self):
        _png(self.current / "home-light.png", (0, 0, 0))
        _png(self.current / "progress-light.png", (5, 5, 5))
        self.assertEqual(_run(self.baseline, self.current, self.report, "--update", "--ignore", "progress-*").returncode, 0)
        self.assertTrue((self.baseline / "home-light.png").exists())
        self.assertFalse((self.baseline / "progress-light.png").exists())

    def test_tiny_rendering_noise_is_tolerated(self):
        _png(self.baseline / "a-dark.png", (10, 10, 10))
        _png(self.current / "a-dark.png", (12, 11, 10))  # 玻璃模糊造成的 1–2 階雜訊
        self.assertEqual(_run(self.baseline, self.current, self.report).returncode, 0)

    def test_visible_color_change_still_fails(self):
        _png(self.baseline / "a-dark.png", (10, 10, 10))
        _png(self.current / "a-dark.png", (30, 10, 10))
        self.assertEqual(_run(self.baseline, self.current, self.report).returncode, 1)


if __name__ == "__main__":
    unittest.main()
