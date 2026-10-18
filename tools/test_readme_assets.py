from pathlib import Path
from urllib.parse import unquote
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

# inline 連結 ](…)、HTML src=/href=、reference-style [ref]: … 都算；有 scheme 的（https:、mailto:）是外部連結。
LINK_PATTERN = re.compile(r"""(?:(?:src|href)=["']|\]\(|^\[[^\]]+\]:\s*)([^"')#\s]+)""", re.MULTILINE)


class ReadmeAssetTests(unittest.TestCase):
    def test_every_local_link_and_image_exists(self):
        targets = [
            unquote(target.removeprefix("./"))
            for target in LINK_PATTERN.findall(README)
            if not re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE)
        ]
        self.assertTrue(targets)
        for target in targets:
            self.assertTrue((ROOT / target).exists(), target)

    def test_every_readme_screenshot_is_referenced(self):
        # 只看圖檔：macOS Finder 會在資料夾留 .DS_Store，不能讓它誤報。
        screenshots = [
            path for path in (ROOT / "docs/readme").iterdir() if path.suffix.lower() in IMAGE_SUFFIXES
        ]
        self.assertTrue(screenshots)
        for path in screenshots:
            self.assertIn(f"docs/readme/{path.name}", README, path.name)


if __name__ == "__main__":
    unittest.main()
