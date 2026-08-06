#!/usr/bin/env python3
"""blog/index.html -> build/index.json   -- THE SPINE of the migration.

This file is authoritative for two things nothing else can supply:

  1. SEMESTER GROUPING. The label is data, not a function of the date: this
     index files 19 June 2015 under "Spring 2015" but 12 July 2023 under its
     own "Summer 2023". No date->term rule reproduces both.
  2. THE CANONICAL TALK LIST. 330 <li class="bloglink"> entries under 30 <h3>
     headings, including 106 pre-2015 talks that have no local page at all.

Usage:  python3 extract_blog_index.py [--legacy DIR] [--out build/index.json]
"""

import argparse
import json
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import clean_text, parse_date_multi, read_text, term_key  # noqa: E402

DEFAULT_LEGACY = os.path.expanduser("~/src/statml-old")


def extract(legacy_dir):
    path = os.path.join(legacy_dir, "blog", "index.html")
    text, encoding = read_text(path)
    soup = BeautifulSoup(text, "html.parser")

    entries, terms = [], []
    current = None
    order = 0

    # <h3> headings and <li class="bloglink"> are siblings in one flat <ul>,
    # so a document-order walk is the only thing that preserves the grouping.
    for node in soup.find_all(["h3", "li"]):
        if node.name == "h3":
            name = clean_text(node.get_text())
            if not name:
                continue
            current = {"key": term_key(name), "name": name, "count": 0}
            terms.append(current)
            continue

        if "bloglink" not in (node.get("class") or []):
            continue
        if current is None:
            print("  WARN: <li> before any <h3>, skipped", file=sys.stderr)
            continue

        dates = node.find_all("span", class_="date")
        link = node.find("a")
        # markup is: <span class=date>DATE</span> <a>TITLE</a> <span class=date>SPEAKER</span>
        date_raw = clean_text(dates[0].get_text()) if dates else None
        speaker_raw = clean_text(dates[1].get_text()) if len(dates) > 1 else None
        title = clean_text(link.get_text()) if link else clean_text(node.get_text())
        href = link.get("href").strip() if link and link.get("href") else None

        date, date_note = parse_date_multi(date_raw)
        order += 1
        current["count"] += 1

        # The 2009-2010 row is not a talk -- it is the archive's own "And there
        # was once a beginning!" placeholder, pointing at the dead
        # statml.cs.cmu.edu. Keep it out of the talk counts.
        kind = "placeholder" if not date and not speaker_raw else "talk"

        entries.append({
            "order": order,
            "term": current["key"],
            "term_name": current["name"],
            "kind": kind,
            "date_raw": date_raw,
            "date": date.isoformat() if date else None,
            "date_note": date_note,
            "title": title,
            "speaker_raw": speaker_raw,
            "href": href,
            "external": bool(href and re.match(r"^https?://", href)),
        })

    return {"source": "blog/index.html", "encoding": encoding,
            "terms": terms, "entries": entries}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", default=DEFAULT_LEGACY)
    ap.add_argument("--out", default="build/index.json")
    args = ap.parse_args()

    data = extract(args.legacy)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)

    e = data["entries"]
    ext = sum(1 for x in e if x["external"])
    nodate = sum(1 for x in e if not x["date"] and x["kind"] != "placeholder")
    print("terms    %d" % len(data["terms"]))
    print("entries  %d  (local %d, external %d)" % (len(e), len(e) - ext, ext))
    if nodate:
        print("WARN     %d entries with unparseable dates:" % nodate)
        for x in e:
            if not x["date"] and x["kind"] != "placeholder":
                print("           [%s] %r -> %s" % (x["term"], x["date_raw"], x["title"][:52]))
    print("wrote    %s" % args.out)


if __name__ == "__main__":
    main()
