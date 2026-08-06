#!/usr/bin/env python3
"""snapshots/sheet-*.csv -> build/sheet.json

The live schedule. Eight semester blocks stacked in ONE tab, each introduced by
a "Schedule (Term Year)" cell whose second line carries the default time and
room ("Time & location: NSH 3305 2-3:30pm").

This is the ONLY source for Fall 2025 and Spring 2026 -- neither was ever
archived to the site -- and for the Fall 2026 skeleton.

Parses the frozen SNAPSHOT, never the live sheet: the live one already drifted
once mid-planning (two Fall 2025 date cells changed hours apart).

Usage:  python3 extract_sheet.py [--snapshot PATH] [--out build/sheet.json]
"""

import argparse
import csv
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (ROOM_RE, check_weekday, classify_row, clean_text,  # noqa: E402
                    parse_date_cell, split_speaker_note, term_key)

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK_RE = re.compile(r"Schedule\s*\(([^)]+)\)", re.I)
TIME_RE = re.compile(r"(\d{1,2}(?::\d{2})?\s*[-–—]\s*\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?|"
                     r"\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?[-–—]\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?|"
                     r"\d{1,2}\s*[-–—]\s*\d{1,2}\s*[ap]\.?m\.?)", re.I)
HEADER_CELLS = {"week", "date", "speaker", "presenter", "title", "paper title",
                "topic", "abstract"}


def parse_header(cell):
    """'Schedule (Fall 2025)\\n\\nTime & location: NSH 3305 2-3:30pm' -> dict."""
    name = clean_text(BLOCK_RE.search(cell).group(1))
    rest = cell.split("\n", 1)[1] if "\n" in cell else ""
    rest = clean_text(rest)
    room = None
    rm = ROOM_RE.search(rest or "")
    if rm:
        room = clean_text(rm.group(1))
    tm = TIME_RE.search(rest or "")
    weekday = None
    for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
        if rest and re.search(d[:-1] + r"s?\b", rest, re.I):
            weekday = d
            break
    return {"key": term_key(name), "name": name, "note": rest or None,
            "default_room": room, "default_time": clean_text(tm.group(1)) if tm else None,
            "default_weekday": weekday}


def extract(snapshot):
    with open(snapshot, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))

    blocks, entries, warnings = [], [], []
    current = None

    for i, raw in enumerate(rows):
        cells = [clean_text(c) or "" for c in raw]
        first = cells[0] if cells else ""

        if BLOCK_RE.search(raw[0] if raw else ""):
            current = parse_header(raw[0])
            current["row"] = i
            current["count"] = 0
            blocks.append(current)
            continue
        if not current or not first:
            continue
        if first.lower() in HEADER_CELLS:
            continue

        year = None
        m = re.search(r"(\d{4})", current["name"])
        if m:
            year = int(m.group(1))
        # Spring terms in a "Spring YYYY" block are in YYYY; Fall likewise.
        dc = parse_date_cell(raw[0], year)
        if not dc["date"]:
            continue

        speaker_cell = cells[1] if len(cells) > 1 else ""
        kind, label = classify_row(speaker_cell)
        sp = split_speaker_note(speaker_cell) if kind == "talk" else {
            "name": None, "affiliation": None, "room": None, "weekday": None, "note": None}

        title = cells[2] if len(cells) > 2 else ""
        abstract = cells[3] if len(cells) > 3 else ""
        if title.strip().upper() in ("NA", "N/A", "TBD", "TBA"):
            title = ""
        if abstract.strip().upper() in ("NA", "N/A"):
            abstract = ""
        if kind == "talk" and not sp["name"]:
            kind = "tbd"

        weekday = dc["weekday"] or sp["weekday"]
        if weekday and not check_weekday(dc["date"], weekday):
            warnings.append("row %d: %s is a %s, sheet says %s" % (
                i, dc["date"], dc["date"].strftime("%A"), weekday))

        current["count"] += 1
        entries.append({
            "row": i,
            "term": current["key"],
            "term_name": current["name"],
            "kind": kind,
            "label": label,
            "date": dc["date"].isoformat(),
            "date_raw": clean_text(raw[0]),
            "weekday_override": weekday,
            "room": dc["room"] or sp["room"],
            "note": dc["note"] or sp["note"],
            "speaker_raw": sp["name"],
            "affiliation": sp["affiliation"],
            "title": title or None,
            "abstract": abstract or None,
        })

    return {"source": os.path.basename(snapshot), "blocks": blocks,
            "entries": entries, "warnings": warnings}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    ap.add_argument("--out", default="build/sheet.json")
    args = ap.parse_args()

    snap = args.snapshot or sorted(glob.glob(
        os.path.join(HERE, "snapshots", "sheet-*.csv")))[-1]
    data = extract(snap)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)

    print("snapshot %s\n" % os.path.basename(snap))
    for b in data["blocks"]:
        talks = sum(1 for e in data["entries"] if e["term"] == b["key"] and e["kind"] == "talk")
        print("  %-12s %-13s rows=%2d talks=%2d  room=%-11s time=%-14s" % (
            b["key"], b["name"], b["count"], talks,
            b["default_room"] or "-", b["default_time"] or "-"))
    kinds = {}
    for e in data["entries"]:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print("\nentries %d  %s" % (len(data["entries"]), kinds))
    for w in data["warnings"]:
        print("  WEEKDAY MISMATCH  %s" % w)
    print("wrote  %s" % args.out)


if __name__ == "__main__":
    main()
