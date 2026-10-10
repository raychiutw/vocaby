#!/usr/bin/env python3
"""比對截圖目錄與基準圖。

有差異、缺圖或多圖時回傳 1,並把「基準 | 目前 | 差異(放大)」並排圖寫進 REPORT。
--update 會用 CURRENT 取代 BASELINE:先在暫存目錄建好並驗證,成功才替換,失敗不動既有基準。
--ignore 排除符合 GLOB 的檔名(不比對、也不納入基準)。

比對的寬鬆處:
- 每通道 4 階以內的差異視為相同(Liquid Glass 模糊運算的渲染雜訊)。這也代表整體色偏 4 階以內不會被抓到。
- 畫面最底部 2% 不參與比對(Home Indicator,模擬器裡時有時無)。
"""
import argparse
from fnmatch import fnmatch
from pathlib import Path
import shutil
import sys

from PIL import Image, ImageChops

# 半透明玻璃(Liquid Glass)的模糊運算每次渲染會有 1–2 階的雜訊,低於此值視為相同
TOLERANCE = 4

# 最底部這個比例的帶狀區域是 Home Indicator(系統覆蓋層,在模擬器裡時有時無),不參與比對
HOME_INDICATOR_FRACTION = 0.02

# 報告中的差異圖放大倍率,讓 5–10 階的差異也看得見
DIFF_GAIN = 16


def without_home_indicator(im: Image.Image) -> Image.Image:
    strip = int(im.height * HOME_INDICATOR_FRACTION)
    if strip == 0:
        return im
    im = im.copy()
    im.paste((0, 0, 0), (0, im.height - strip, im.width, im.height))
    return im


def same(baseline: Image.Image, current: Image.Image) -> bool:
    if baseline.size != current.size:
        return False
    diff = ImageChops.difference(without_home_indicator(baseline), without_home_indicator(current))
    return diff.point(lambda v: 255 if v > TOLERANCE else 0).getbbox() is None


def side_by_side(baseline: Image.Image, current: Image.Image) -> Image.Image:
    current = current.resize(baseline.size) if current.size != baseline.size else current
    diff = ImageChops.difference(baseline, current).point(lambda v: min(255, v * DIFF_GAIN))
    out = Image.new("RGB", (baseline.width * 3, baseline.height))
    for i, im in enumerate((baseline, current, diff)):
        out.paste(im, (i * baseline.width, 0))
    return out


def ignored(name: str, patterns: list[str]) -> bool:
    return any(fnmatch(name, g) for g in patterns)


def update_baseline(baseline_dir: Path, current_dir: Path, patterns: list[str]) -> int:
    if not any(not ignored(p.name, patterns) for p in current_dir.glob("*.png")):
        print(f"{current_dir} 沒有截圖,不更新基準圖", file=sys.stderr)
        return 1

    staging = baseline_dir.with_name(baseline_dir.name + ".new")
    shutil.rmtree(staging, ignore_errors=True)
    try:
        shutil.copytree(current_dir, staging, ignore=shutil.ignore_patterns(*patterns))
        for png in staging.glob("*.png"):
            with Image.open(png) as im:
                im.verify()
    except Exception as error:  # 複製或驗證失敗:丟掉暫存,既有基準原封不動
        shutil.rmtree(staging, ignore_errors=True)
        print(f"更新基準圖失敗,既有基準未變動:{error}", file=sys.stderr)
        return 1

    backup = baseline_dir.with_name(baseline_dir.name + ".old")
    shutil.rmtree(backup, ignore_errors=True)
    if baseline_dir.exists():
        baseline_dir.rename(backup)
    staging.rename(baseline_dir)
    shutil.rmtree(backup, ignore_errors=True)
    return 0


def compare(baseline_dir: Path, current_dir: Path, report_dir: Path, patterns: list[str]) -> int:
    shutil.rmtree(report_dir, ignore_errors=True)
    report_dir.mkdir(parents=True)
    names = {
        p.name for d in (baseline_dir, current_dir) for p in d.glob("*.png") if not ignored(p.name, patterns)
    }
    failed = False
    for name in sorted(names):
        base, cur = baseline_dir / name, current_dir / name
        if not cur.exists():
            print(f"MISSING {name}")
        elif not base.exists():
            print(f"NEW     {name}")
        else:
            b, c = Image.open(base).convert("RGB"), Image.open(cur).convert("RGB")
            if same(b, c):
                print(f"SAME    {name}")
                continue
            side_by_side(b, c).save(report_dir / name)
            note = f" (尺寸 {b.size} -> {c.size},報告中的目前圖已縮放)" if b.size != c.size else ""
            print(f"CHANGED {name}{note}")
        failed = True
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="比對截圖目錄與基準圖", epilog=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--update", action="store_true", help="用 CURRENT 取代 BASELINE")
    parser.add_argument("--ignore", action="append", default=[], metavar="GLOB", help="排除符合的檔名,可重複")
    args = parser.parse_args(argv)

    if args.update:
        return update_baseline(args.baseline, args.current, args.ignore)
    return compare(args.baseline, args.current, args.report, args.ignore)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
