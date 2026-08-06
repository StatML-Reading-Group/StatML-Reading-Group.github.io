#!/usr/bin/env python3
"""blog/**/*.html -> build/pages.json   -- the abstracts live here.

223 talk pages in three markup eras, all sharing <p class="meta"> and a
"Speaker:" marker:

  A  13 pages  2015-01 .. 2015-06   <h3> title,  meta "22 Jan 2015"
  B 144 pages  2015-09 .. 2022-10   <h4> title,  meta "Nov 18 (Wednesday) at 1:30 pm<br>NSH-1507"
  C  66 pages  2022-10 .. 2025-04   <h4> title,  meta "12 Nov, 2024, 3:30-4:30 pm, GHC 6501"

Two traps:
  * 127 of the metas carry NO YEAR. The year comes from the file path, never
    from the meta. (See common.meta_text for the unclosed-<p> trap.)
  * Filename stems are NOT identity: blog/2015/11/18/samy.html is a talk by
    Kirthevasan Kandasamy, and arun.html resolves to four different people
    across four years. Always read the Speaker: line.

Usage:  python3 extract_blog_pages.py [--legacy DIR] [--out build/pages.json]
"""

import argparse
import glob
import json
import os
import re
import sys
import urllib.parse

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (ROOM_RE, WEEKDAYS, clean_text, parse_date,  # noqa: E402
                    meta_text, read_text, rel_path)

DEFAULT_LEGACY = os.path.expanduser("~/src/statml-old")

PATH_RE = re.compile(r"blog/(\d{4})/(\d{1,2})/(\d{1,2})/([^/]+)\.html$")
TIME_RE = re.compile(r"(\d{1,2}(?::\d{2})?\s*(?:[-–—]{1,2}\s*\d{1,2}(?::\d{2})?)?\s*[ap]\.?m\.?)", re.I)


def _strip_label(text, label):
    """'Speaker: Jane Doe' -> 'Jane Doe'."""
    return clean_text(re.sub(r"^\s*%s\s*:?\s*" % label, "", text, flags=re.I))


def extract_one(path, legacy_dir):
    text, encoding = read_text(path)
    soup = BeautifulSoup(text, "html.parser")
    rel = rel_path(legacy_dir, path)

    m = PATH_RE.search(rel)
    if not m:
        return None
    year, month, day, stem = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)

    # ---- title: first <h3>/<h4> that is not a commented-out or nav heading
    title = None
    for tag in soup.find_all(["h3", "h4"]):
        t = clean_text(tag.get_text())
        if t and t.lower() not in ("people", "list of past talks", "home", "archive"):
            title = t
            title_link = tag.find("a")
            break
    else:
        title_link = None
    paper_url = title_link.get("href") if title_link and title_link.get("href") else None

    # ---- meta line (see common.meta_text -- the <p> is unclosed pre-2023)
    meta_tag = soup.find("p", class_="meta")
    meta = meta_text(meta_tag) if meta_tag else None

    date = parse_date(meta, fallback_year=year) if meta else None
    path_date = "%04d-%02d-%02d" % (year, month, day)

    room = None
    if meta:
        rm = ROOM_RE.search(meta)
        if rm:
            room = clean_text(rm.group(1))
        else:
            rm2 = re.search(r"\b([A-Z]{2,4}[\s-]?\d{3,4}[A-Z]?)\b", meta)
            room = clean_text(rm2.group(1)) if rm2 else None
    time_m = TIME_RE.search(meta) if meta else None
    weekday = next((d for d in WEEKDAYS if meta and d.lower() in meta.lower()), None)

    # ---- speaker + abstract, from the post body
    body = soup.find("div", class_="post") or soup
    body_text = body.get_text("\n")
    speaker = None
    sm = re.search(r"Speaker\s*:\s*(.+)", body_text)
    if sm:
        speaker = clean_text(sm.group(1).split("\n")[0])

    abstract = None
    abs_tag = None
    for p in body.find_all("p"):
        if re.match(r"^\s*Abstract\s*:", p.get_text(), flags=re.I):
            abs_tag = p
            break
    if abs_tag is not None:
        inner = abs_tag.decode_contents()
        inner = re.sub(r"^\s*<b>\s*Abstract\s*:?\s*</b>\s*:?\s*", "", inner, flags=re.I)
        inner = re.sub(r"^\s*Abstract\s*:?\s*", "", inner, flags=re.I)
        abstract = clean_text(inner) or None
    else:
        # 3 pages have no "Abstract:" marker -- the abstract is the second <p>
        ps = [p for p in body.find_all("p") if "meta" not in (p.get("class") or [])]
        cands = [clean_text(p.get_text()) for p in ps]
        cands = [c for c in cands if c and not re.match(r"^\s*Speaker\s*:", c, flags=re.I)]
        abstract = cands[0] if cands else None

    # ---- LaTeX rendered as images by an http-only CDN (mixed content on HTTPS)
    latex = []
    for img in body.find_all("img"):
        src = img.get("src") or ""
        if "codecogs" in src and "latex?" in src:
            latex.append(urllib.parse.unquote(src.split("latex?", 1)[1]))

    return {
        "file": rel,
        "encoding": encoding,
        "stem": stem,
        "path_date": path_date,
        "url": "/" + rel,
        "title": title,
        "speaker_raw": speaker,
        "abstract": abstract,
        "abstract_from_marker": abs_tag is not None,
        "meta_raw": meta,
        "date": date.isoformat() if date else None,
        "date_matches_path": bool(date and date.isoformat() == path_date),
        "room": room,
        "time": clean_text(time_m.group(1)) if time_m else None,
        "weekday": weekday,
        "paper_url": paper_url,
        "latex": latex,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", default=DEFAULT_LEGACY)
    ap.add_argument("--out", default="build/pages.json")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.legacy, "blog", "*", "*", "*", "*.html")))
    pages, skipped = [], []
    for f in files:
        if f.endswith("~"):
            skipped.append((rel_path(args.legacy, f), "editor backup"))
            continue
        rec = extract_one(f, args.legacy)
        if rec is None:
            skipped.append((rel_path(args.legacy, f), "path did not match"))
        else:
            pages.append(rec)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"pages": pages, "skipped": skipped}, fh, indent=1, ensure_ascii=False)

    no_title = [p for p in pages if not p["title"]]
    no_speaker = [p for p in pages if not p["speaker_raw"]]
    no_abstract = [p for p in pages if not p["abstract"]]
    no_marker = [p for p in pages if p["abstract"] and not p["abstract_from_marker"]]
    date_conflict = [p for p in pages if p["date"] and not p["date_matches_path"]]
    cp1252 = [p for p in pages if p["encoding"] != "utf-8"]
    latex = [p for p in pages if p["latex"]]

    print("pages parsed      %d   (skipped %d)" % (len(pages), len(skipped)))
    print("  no title        %d" % len(no_title))
    print("  no speaker      %d" % len(no_speaker))
    print("  no abstract     %d" % len(no_abstract))
    print("  abstract w/o marker %d" % len(no_marker))
    print("  cp1252          %d   %s" % (len(cp1252), [p["file"] for p in cp1252]))
    print("  latex images    %d pages, %d formulas" % (len(latex), sum(len(p["latex"]) for p in latex)))
    print("  date != path    %d" % len(date_conflict))
    for p in date_conflict:
        print("      %-34s meta=%-12s path=%s" % (p["file"], p["date"], p["path_date"]))
    for p in no_speaker + no_title:
        print("      MISSING FIELD %s" % p["file"])
    print("wrote  %s" % args.out)


if __name__ == "__main__":
    main()
