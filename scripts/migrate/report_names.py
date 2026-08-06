#!/usr/bin/env python3
"""Report every speaker surface form across all sources, clustered by slug.

Input for hand-writing aliases.yaml. Prints:
  1. slugs with MORE THAN ONE surface form  -- already auto-merged, sanity-check
  2. slugs that differ by a small edit      -- candidate merges needing a human
  3. every slug not present in people.csv   -- external speakers

Usage:  python3 report_names.py [--legacy DIR]
"""

import argparse
import csv
import difflib
import io
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import clean_text, read_text, slugify  # noqa: E402

DEFAULT_LEGACY = os.path.expanduser("~/src/statml-old")


def collect():
    forms = defaultdict(set)   # slug -> {surface form}
    where = defaultdict(set)   # slug -> {source}

    def add(raw, src):
        if not raw:
            return
        s = slugify(raw)
        if s:
            forms[s].add(clean_text(raw))
            where[s].add(src)

    idx = json.load(open("build/index.json"))
    for e in idx["entries"]:
        add(e.get("speaker_raw"), "index")
    pg = json.load(open("build/pages.json"))
    for p in pg["pages"]:
        add(p.get("speaker_raw"), "page")
    cs = json.load(open("build/csvs.json"))
    for r in cs["rows"]:
        add(r.get("speaker_raw"), "csv")
    sh = json.load(open("build/sheet.json"))
    for e in sh["entries"]:
        add(e.get("speaker_raw"), "sheet")
    aa = json.load(open("build/aarti.json"))
    for t in aa["talks"]:
        add(t.get("speaker_raw"), "aarti")
    return forms, where


def roster(legacy_dir):
    text, _ = read_text(os.path.join(legacy_dir, "people.csv"))
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        first = clean_text(row.get("FirstName"))
        last = clean_text(row.get("LastName"))
        if not (first or last):
            continue
        full = ("%s %s" % (first or "", last or "")).strip()
        s = slugify(full)
        if s:
            out[s] = {"name": full, "type": clean_text(row.get("Type")),
                      "position": clean_text(row.get("Position")),
                      "affiliation": clean_text(row.get("Affiliation1")),
                      "url": clean_text(row.get("Webpage")),
                      "img": clean_text(row.get("ImgPath"))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", default=DEFAULT_LEGACY)
    args = ap.parse_args()

    forms, where = collect()
    ppl = roster(args.legacy)

    print("=" * 78)
    print("SPEAKER SLUGS: %d   ROSTER SLUGS: %d   overlap: %d" % (
        len(forms), len(ppl), len(set(forms) & set(ppl))))
    print("=" * 78)

    multi = {s: v for s, v in forms.items() if len(v) > 1}
    print("\n--- [1] AUTO-MERGED: one slug, several surface forms (%d) ---" % len(multi))
    for s in sorted(multi):
        print("  %-30s %s" % (s, sorted(multi[s])))

    print("\n--- [2] NEAR-MISS PAIRS: candidate merges, NEED HUMAN REVIEW ---")
    keys = sorted(set(forms) | set(ppl))
    seen = set()
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if (a, b) in seen:
                continue
            r = difflib.SequenceMatcher(None, a, b).ratio()
            if r >= 0.86:
                seen.add((a, b))
                fa = sorted(forms.get(a, {ppl.get(a, {}).get("name", "")}))
                fb = sorted(forms.get(b, {ppl.get(b, {}).get("name", "")}))
                ra = " roster" if a in ppl else ""
                rb = " roster" if b in ppl else ""
                print("  %.2f  %-26s%-8s %s" % (r, a, ra, fa))
                print("        %-26s%-8s %s" % (b, rb, fb))

    ext = sorted(set(forms) - set(ppl))
    print("\n--- [3] SPEAKERS NOT ON THE ROSTER (%d) ---" % len(ext))
    for s in ext:
        print("  %-30s %-46s %s" % (s, sorted(forms[s])[0][:46], sorted(where[s])))

    orphan = sorted(set(ppl) - set(forms))
    print("\n--- [4] ROSTER MEMBERS WHO NEVER SPOKE (%d) ---" % len(orphan))
    for s in orphan:
        print("  %-30s %-26s %s" % (s, ppl[s]["name"], ppl[s]["type"]))


if __name__ == "__main__":
    main()
