#!/usr/bin/env python3
"""snapshots/aarti-*/ -> build/aarti.json   -- the pre-2015 era.

The 106 talks from Fall 2010 through Spring 2014 have no local page; the site's
archive index links out to www.cs.cmu.edu/~aarti/SMLRG/. Those pages are a
different genre -- a reading group in the literal sense, where the group read a
PAPER each week:

    <tr><td><b>Sept 1</b></td>
        <td>VC bounds on the cardinality of ... (<a href="...">pdf</a>)<br>
            <i>Authors:</i> Lee-Ad Gottlieb, Leonid Kontorovich, Elchanan Mossel<br>
            <i>Presenter:</i> Shiva Kaul<br></td></tr>

So they carry paper_url and paper_authors, which exist in NO other source, and
they carry no abstracts, which is not a migration loss -- they never had any.

Parses the frozen snapshot. These pages live on a personal faculty directory
and will eventually vanish.

Usage:  python3 extract_aarti.py [--dir PATH] [--out build/aarti.json]
"""

import argparse
import glob
import json
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (ROOM_RE, classify_row, clean_text, parse_date,  # noqa: E402
                    read_text)

HERE = os.path.dirname(os.path.abspath(__file__))

# index_Fall10.html -> ("fall", 2010)
FILE_RE = re.compile(r"index_(Fall|Spring|Summer)(\d{2})\.html$", re.I)


def term_from_filename(name):
    m = FILE_RE.search(name)
    if not m:
        return None, None
    season = m.group(1).lower()
    year = 2000 + int(m.group(2))
    return "%s%d" % (season, year), "%s %d" % (season.capitalize(), year)


def extract_one(path):
    text, encoding = read_text(path)
    soup = BeautifulSoup(text, "html.parser")
    fname = os.path.basename(path)
    key, name = term_from_filename(fname)
    if not key:
        return None

    year = int(re.search(r"(\d{4})", name).group(1))

    # Header defaults: "<b>Room:</b> 6121 Gates-Hillman Center", "<b>Time:</b> 2-3 pm Wednesday"
    head = clean_text(soup.get_text(" ")[:900]) or ""
    room = None
    rm = re.search(r"Room:\s*([^()<]{3,48}?)\s*(?:\(|Time:|$)", head, re.I)
    if rm:
        room = clean_text(rm.group(1))
    elif ROOM_RE.search(head):
        room = clean_text(ROOM_RE.search(head).group(1))
    tm = re.search(r"Time:\s*([^<]{3,40}?)\s*(?:SCHEDULE|$)", head, re.I)
    default_time = clean_text(tm.group(1)) if tm else None

    talks = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) != 2:
            continue
        label = clean_text(tds[0].get_text(" "))
        if not label or label.upper().startswith("SCHEDULE"):
            continue
        date = parse_date(label, fallback_year=year)
        # Spring terms span Jan-May of the stated year; Fall terms Aug-Dec.
        # A "Jan 12" inside index_Fall13 would be wrong -- flag rather than guess.
        if not date:
            continue

        cell = tds[1]
        body_html = cell.decode_contents()
        first_line = re.split(r"<br\s*/?>", body_html)[0]
        frag = BeautifulSoup(first_line, "html.parser")

        paper_url = None
        for a in frag.find_all("a"):
            if clean_text(a.get_text()).lower() in ("pdf", "paper", "link", "arxiv"):
                paper_url = a.get("href")
                a.decompose()
        title = clean_text(frag.get_text(" "))
        title = re.sub(r"\(\s*\)\s*$", "", title).strip(" ()")

        cell_text = clean_text(cell.get_text("\n")) or ""
        am = re.search(r"Authors?\s*:\s*(.+?)(?:\s*Presenters?\s*:|$)", cell_text, re.I)
        pm = re.search(r"Presenters?\s*:\s*(.+?)$", cell_text, re.I)
        presenter = clean_text(pm.group(1)) if pm else None
        if presenter:
            presenter = re.split(r"\s{2,}|;", presenter)[0].strip()

        if not title and not presenter:
            continue

        talks.append({
            "term": key,
            "term_name": name,
            "date": date.isoformat(),
            "date_raw": label,
            "title": title or None,
            "speaker_raw": presenter,
            "paper_url": paper_url,
            "paper_authors": clean_text(am.group(1)) if am else None,
            "source_page": fname,
        })

    return {"file": fname, "encoding": encoding, "term": key, "term_name": name,
            "default_room": room, "default_time": default_time, "talks": talks}


def extract_fall2014(path):
    """The Fall 2014 schedule lives in its OWN Google Sheet, not an HTML page.

    schedule.html is a DataTables view whose rows are fetched at runtime from a
    (now-404) gdata feed; the underlying sheet is still exportable as CSV. It is
    the richest pre-2015 source we have -- it carries speaker HOMEPAGES and
    reading-material links that appear nowhere else in the corpus.
    """
    import csv as _csv

    talks = []
    with open(path, newline="", encoding="utf-8") as fh:
        for i, row in enumerate(_csv.DictReader(fh)):
            date = parse_date(clean_text(row.get("date0")))
            if not date:
                continue
            name = clean_text(row.get("Name"))
            topic = clean_text(row.get("topic"))
            kind, label = classify_row(name or topic or "")

            details = row.get("details") or ""
            paper_url, paper_authors = None, None
            dm = BeautifulSoup(details, "html.parser")
            for a in dm.find_all("a"):
                href = a.get("href") or ""
                if href.startswith("http") and "statweb" not in href and "~" not in href:
                    paper_url = href
                    break
            rm = re.search(r"Reading material\s*:?\s*([^<]{3,160})", details, re.I)
            if rm:
                paper_authors = clean_text(rm.group(1)).rstrip(",. ")

            room = None
            lm = re.search(r"Location\s*</strong>\s*:?\s*([^<]{3,48})", details, re.I)
            if lm:
                room = clean_text(lm.group(1))

            talks.append({
                "term": "fall2014",
                "term_name": "Fall 2014",
                "kind": kind,
                "label": label,
                "date": date.isoformat(),
                "date_raw": clean_text(row.get("date0")),
                "title": topic or None,
                "speaker_raw": name if kind == "talk" else None,
                "speaker_url": clean_text(row.get("webpage")) or None,
                "paper_url": paper_url,
                "paper_authors": paper_authors,
                "room": room,
                "source_page": os.path.basename(path),
            })
    return talks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--out", default="build/aarti.json")
    args = ap.parse_args()

    d = args.dir or sorted(glob.glob(os.path.join(HERE, "snapshots", "aarti-*")))[-1]
    pages, talks = [], []
    for f in sorted(glob.glob(os.path.join(d, "*.html"))):
        rec = extract_one(f)
        if rec is None:
            print("  skip (no term in filename): %s" % os.path.basename(f))
            continue
        pages.append({k: v for k, v in rec.items() if k != "talks"})
        talks.extend(rec["talks"])
        with_pdf = sum(1 for t in rec["talks"] if t["paper_url"])
        print("  %-20s %-12s talks=%2d  pdf=%2d  room=%-28s time=%s" % (
            rec["file"], rec["term"], len(rec["talks"]), with_pdf,
            (rec["default_room"] or "-")[:28], rec["default_time"] or "-"))

    f14 = sorted(glob.glob(os.path.join(HERE, "snapshots", "sheet-fall2014-*.csv")))
    if f14:
        got = extract_fall2014(f14[-1])
        talks.extend(got)
        real = sum(1 for t in got if t["kind"] == "talk")
        print("  %-20s %-12s talks=%2d  pdf=%2d  (speaker homepages: %d)" % (
            os.path.basename(f14[-1])[:20], "fall2014", real,
            sum(1 for t in got if t["paper_url"]),
            sum(1 for t in got if t.get("speaker_url"))))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"pages": pages, "talks": talks}, fh, indent=1, ensure_ascii=False)

    print("\ntalks %d   with paper_url %d   with authors %d   missing presenter %d" % (
        len(talks),
        sum(1 for t in talks if t["paper_url"]),
        sum(1 for t in talks if t["paper_authors"]),
        sum(1 for t in talks if not t["speaker_raw"])))
    print("wrote  %s" % args.out)


if __name__ == "__main__":
    main()
