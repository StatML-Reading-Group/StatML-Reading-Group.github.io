#!/usr/bin/env python3
"""Fail if any colour token drops below WCAG AA against its own theme background.

A str.replace over the stylesheet once copied a light-mode link colour into
the dark block, leaving links at 2.49:1 on a dark page -- a change that looks
fine in light mode and is invisible until someone toggles the theme.
"""

import re
import sys


def lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lum(h):
    h = h.lstrip("#")
    r, g, b = (lin(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# decorative or surface tokens: not text, so AA does not apply
EXEMPT = {"bg", "bg-elev", "bg-sunk", "nav-bg", "hairline", "hairline-strong",
          "border-mid", "text-faint", "shadow-soft"}

css = open("libs/custom/my_css.css", encoding="utf-8").read()
light_start = css.index(":root {\n  color-scheme: light;")
dark_start = css.index(':root[data-theme="dark"]')
dark_end = css.index("/* ================ Type scale")
blocks = {
    "light": css[light_start:dark_start],
    "dark": css[dark_start:dark_end],
}

fails = []
for theme, block in blocks.items():
    tok = {m.group(1): m.group(2)
           for m in re.finditer(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block)}
    bg = tok["bg"]
    for name, val in sorted(tok.items()):
        if name in EXEMPT:
            continue
        r = ratio(val, bg)
        if r < 4.5:
            fails.append("%s/--%s %s is %.2f:1 on %s" % (theme, name, val, r, bg))

if fails:
    print("::error::%d colour token(s) below AA" % len(fails))
    for f in fails:
        print("  " + f)
    sys.exit(1)
print("all colour tokens AA or better in both themes")
