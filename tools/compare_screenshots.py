#!/usr/bin/env python3
"""比對截圖目錄與基準圖。用法: compare_screenshots.py BASELINE CURRENT REPORT [--update] [--ignore GLOB]...

有差異、缺圖或多圖時回傳 1,並把「基準 | 目前 | 差異」並排圖寫進 REPORT。
--update 會用 CURRENT 取代 BASELINE。--ignore 排除符合 GLOB 的檔名(不比對、也不納入基準)。
"""
from fnmatch import fnmatch
from pathlib import Path
import shutil
import sys

from PIL import Image, ImageChops

# 半透明玻璃(Liquid Glass)的模糊運算每次渲染會有 1–2 階的雜訊,低於此值視為相同
TOLERANCE = 4


def side_by_side(baseline: Image.Image, current: Image.Image) -> Image.Image:
    current = current.resize(baseline.size) if current.size != baseline.size else current
    diff = ImageChops.difference(baseline, current)
    out = Image.new("RGB", (baseline.width * 3, baseline.height))
    for i, im in enumerate((baseline, current, diff)):
        out.paste(im, (i * baseline.width, 0))
    return out


def main(argv: list[str]) -> int:
    update = "--update" in argv
    ignore = [argv[i + 1] for i, a in enumerate(argv) if a == "--ignore"]
    baseline_dir, current_dir, report_dir = (Path(a) for a in argv[:3])

    if update:
        if not any(not any(fnmatch(p.name, g) for g in ignore) for p in current_dir.glob("*.png")):
            sys.exit(f"{current_dir} 沒有截圖,不更新基準圖")
        shutil.rmtree(baseline_dir, ignore_errors=True)
        shutil.copytree(current_dir, baseline_dir, ignore=shutil.ignore_patterns(*ignore))
        return 0

    shutil.rmtree(report_dir, ignore_errors=True)
    report_dir.mkdir(parents=True)
    names = {p.name for d in (baseline_dir, current_dir) for p in d.glob("*.png")
             if not any(fnmatch(p.name, g) for g in ignore)}
    failed = False
    for name in sorted(names):
        base, cur = baseline_dir / name, current_dir / name
        if not cur.exists():
            print(f"MISSING {name}")
        elif not base.exists():
            print(f"NEW     {name}")
        else:
            b, c = Image.open(base).convert("RGB"), Image.open(cur).convert("RGB")
            if b.size == c.size and ImageChops.difference(b, c).point(lambda v: 255 if v > TOLERANCE else 0).getbbox() is None:
                print(f"SAME    {name}")
                continue
            side_by_side(b, c).save(report_dir / name)
            note = f" (尺寸 {b.size} -> {c.size},報告中的目前圖已縮放)" if b.size != c.size else ""
            print(f"CHANGED {name}{note}")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
