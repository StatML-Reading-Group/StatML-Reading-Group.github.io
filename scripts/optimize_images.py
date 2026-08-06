#!/usr/bin/env python3
"""Recompress people photos for the web.

The legacy site shipped 26.8 MB of headshots to render them at 160x200 px --
img/sshekhar.jpg is 4121x5151, about 100x more pixels than are ever displayed.

Targets 320x400 (2x retina) as progressive JPEG q82.

Two constraints that a naive resize gets wrong:

  * 20 of the 93 are ALREADY smaller than 320x400 (martinAzizyan.png is 72x90).
    Scaling "to" the target upscales them: bigger file, blurrier picture. The
    scale factor is clamped at 1.0.
  * Scale to COVER, never ImageOps.fit(), which crops to the exact aspect ratio
    and would cut the top off any photo that is not 4:5.

Usage:
    python3 scripts/optimize_images.py --src ~/src/statml-old --out assets/people
"""

import argparse
import os
import sys

from PIL import Image, ImageOps

# Faculty photos render up to ~180px square, so 440 keeps them crisp at 2x.
TARGET_W, TARGET_H, QUALITY = 440, 550, 82


def convert(src, dst):
    im = ImageOps.exif_transpose(Image.open(src))   # honour camera rotation
    w, h = im.size

    scale = min(1.0, max(TARGET_W / float(w), TARGET_H / float(h)))
    if scale < 1.0:
        im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)

    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")

    im.save(dst, "JPEG", quality=QUALITY, optimize=True,
            progressive=True, subsampling="4:2:0")
    return (w, h), im.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.expanduser("~/src/statml-old"))
    ap.add_argument("--data", default="_data/people.yaml")
    ap.add_argument("--out", default="assets/people")
    ap.add_argument("--roster", help="only convert this roster group")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    import yaml
    with open(args.data, encoding="utf-8") as fh:
        people = yaml.safe_load(fh)

    os.makedirs(args.out, exist_ok=True)
    before = after = 0
    done = skipped = missing = upscale_guard = 0

    for slug, p in sorted(people.items()):
        want = p.get("img")
        if not want:
            continue
        if args.roster and p.get("roster") != args.roster:
            continue
        base = os.path.basename(want)
        # people.yaml already points at the destination; find the ORIGINAL,
        # whose extension may differ (.png/.jpeg/.gif all become .jpg).
        stem = os.path.splitext(base)[0]
        cands = [os.path.join(args.src, "img", stem + e)
                 for e in (".jpg", ".jpeg", ".png", ".gif", ".JPG", ".JPEG", ".PNG")]
        src = next((c for c in cands if os.path.exists(c)), None)
        if not src:
            missing += 1
            print("  MISSING  %-26s (%s)" % (slug, base))
            continue

        dst = os.path.join(args.out, stem + ".jpg")
        sz_before = os.path.getsize(src)
        try:
            (ow, oh), (nw, nh) = convert(src, dst)
        except Exception as exc:                      # noqa: BLE001
            print("  FAILED   %-26s %s" % (slug, exc))
            skipped += 1
            continue
        sz_after = os.path.getsize(dst)
        before += sz_before
        after += sz_after
        done += 1
        if (ow, oh) == (nw, nh):
            upscale_guard += 1
        if not args.quiet:
            print("  %-26s %7.0fK -> %6.0fK   %4dx%-4d -> %3dx%-3d%s" % (
                stem[:26], sz_before / 1024.0, sz_after / 1024.0,
                ow, oh, nw, nh, "   (already small, not upscaled)"
                if (ow, oh) == (nw, nh) else ""))

    print("\n  converted %d   missing %d   failed %d" % (done, missing, skipped))
    print("  left at native size (would have been upscaled): %d" % upscale_guard)
    if before:
        print("  %.2f MB -> %.2f MB   (-%.1f%%)" % (
            before / 1048576.0, after / 1048576.0,
            100.0 * (before - after) / before))
    return 0 if not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
