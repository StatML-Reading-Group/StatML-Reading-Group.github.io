#!/usr/bin/env python3
"""assets/*.csv -> build/csvs.json

Six per-semester schedule files, schema Date,Time,Room,Speaker,Title,Abstract.
These are the input that scripts/make_blog.py consumed to generate the 2022-10
onward blog pages, so they are a strict SUBSET of those pages -- their unique
contribution is pre-split Time and Room columns, which everything else buries
inside a prose meta line.

Two gotchas:
  * spring2023.csv is MISLABELED -- it starts 10/25/2022 and contains Fall 2022
    talks. Term assignment comes from blog/index.html, never from the filename.
  * Line counts lie. Abstracts contain embedded newlines, so 297 "lines" is 139
    rows. Always csv.reader, never splitlines().

Usage:  python3 extract_csvs.py [--legacy DIR] [--out build/csvs.json]
"""

import argparse
import csv
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import clean_text, parse_date, read_text, rel_path  # noqa: E402

DEFAULT_LEGACY = os.path.expanduser("~/src/statml-old")


def extract_one(path, legacy_dir):
    text, encoding = read_text(path)
    rel = rel_path(legacy_dir, path)
    rows = []
    reader = csv.DictReader(io.StringIO(text))
    for i, row in enumerate(reader):
        row = {(k or "").strip(): v for k, v in row.items()}
        date_raw = clean_text(row.get("Date"))
        if not date_raw:
            continue
        date = parse_date(date_raw)
        rows.append({
            "source_file": rel,
            "row": i,
            "date_raw": date_raw,
            "date": date.isoformat() if date else None,
            "time": clean_text(row.get("Time")),
            "room": clean_text(row.get("Room")),
            "speaker_raw": clean_text(row.get("Speaker")),
            "title": clean_text(row.get("Title")),
            "abstract": clean_text(row.get("Abstract")),
        })
    return rel, encoding, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", default=DEFAULT_LEGACY)
    ap.add_argument("--out", default="build/csvs.json")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.legacy, "assets", "*.csv")))
    all_rows, meta = [], []
    for f in files:
        rel, enc, rows = extract_one(f, args.legacy)
        all_rows.extend(rows)
        dates = sorted(r["date"] for r in rows if r["date"])
        meta.append({"file": rel, "encoding": enc, "rows": len(rows),
                     "first": dates[0] if dates else None,
                     "last": dates[-1] if dates else None})
        flag = ""
        if dates:
            stem = os.path.basename(rel).replace(".csv", "")
            yr = dates[0][:4]
            if yr not in stem:
                flag = "   <-- MISLABELED: starts %s" % dates[0]
        print("  %-28s enc=%-7s rows=%3d  %s .. %s%s" % (
            rel, enc, len(rows), dates[0] if dates else "-", dates[-1] if dates else "-", flag))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"files": meta, "rows": all_rows}, fh, indent=1, ensure_ascii=False)

    bad = [r for r in all_rows if not r["date"]]
    print("\ntotal rows %d   unparseable dates %d" % (len(all_rows), len(bad)))
    for r in bad:
        print("   %s row %d: %r" % (r["source_file"], r["row"], r["date_raw"]))
    print("wrote  %s" % args.out)


if __name__ == "__main__":
    main()
