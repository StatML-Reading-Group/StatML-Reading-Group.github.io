#!/usr/bin/env python3
"""build/*.json + people.csv -> _data/   -- the one place sources are reconciled.

Precedence is per FIELD, not per source, and is derived from measured agreement
rather than assumed:

  term       blog_index only     -- the only source with the <h3> grouping, and
                                    it is not derivable (19 Jun 2015 is filed
                                    under Spring 2015; 12 Jul 2023 under its own
                                    Summer 2023)
  date       blog_index > path > page meta
  title      blog_page > blog_index > csv > sheet
                                 -- 1/65 conflict: the CSV truncates Ramdas's
                                    Feb-2023 title at "negative dependence"
  abstract   blog_page > csv > sheet
                                 -- only the page carries rendered HTML links
  time/room  csv > page meta > sheet date-cell > term default
                                 -- only the CSV has real Time/Room columns
  speaker    blog_page > csv > blog_index > sheet
  paper_*    aarti / fall2014 sheet -- exist nowhere else

Join key is (date, speaker_slug). Date alone collides.

Every override is logged to build/conflicts.tsv. Read it end to end.

Usage:  python3 merge.py [--legacy DIR] [--out ../../_data]
"""

import argparse
import csv
import io
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (both_paddings, clean_text, read_text,  # noqa: E402
                    slugify, split_speakers)

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LEGACY = os.path.expanduser("~/src/statml-old")

CONFLICTS = []


def log_conflict(field, key, chosen_src, chosen, other_src, other):
    CONFLICTS.append((field, key, chosen_src, str(chosen)[:400].replace("\t", " "),
                      other_src, str(other)[:400].replace("\t", " ")))


# --------------------------------------------------------------------------
# aliases
# --------------------------------------------------------------------------

def load_aliases():
    with open(os.path.join(HERE, "aliases.yaml"), encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    canon = {}
    for good, bads in (doc.get("merge") or {}).items():
        for bad in (bads or []):
            canon[bad] = good
    never = set()
    for pair in (doc.get("never_merge") or []):
        never.add(tuple(sorted(pair)))
    return canon, never


ALIASES, NEVER_MERGE = load_aliases()


def canon_slug(raw):
    s = slugify(raw)
    return ALIASES.get(s, s)


def speaker_slugs(raw):
    return [ALIASES.get(slugify(p), slugify(p)) for p in split_speakers(raw) if slugify(p)]


# --------------------------------------------------------------------------
# people
# --------------------------------------------------------------------------

# people.csv data-quality fixes, each corroborated by a second source.
PEOPLE_FIXES = {
    "slepcev":  {"name": "Dejan Slepčev"},          # was Slep&#269ev (entity missing ';')
    "farina":   {"swap_name": True},                # First/Last swapped in the CSV
}
TEXT_FIXES = [
    (r"Pennslyvania", "Pennsylvania"),
    (r"Univesity", "University"),
    (r"Havard", "Harvard"),
]


def fix_text(s):
    if not s:
        return s
    for bad, good in TEXT_FIXES:
        s = re.sub(bad, good, s)
    return clean_text(s)


ROSTER_TYPES = {"faculty": "faculty", "postdoc": "postdoc",
                "student": "student", "alumni": "alumni"}


def load_people(legacy_dir):
    text, _ = read_text(os.path.join(legacy_dir, "people.csv"))
    people = OrderedDict()
    for row in csv.DictReader(io.StringIO(text)):
        first = clean_text(row.get("FirstName")) or ""
        last = clean_text(row.get("LastName")) or ""
        if not (first or last):
            continue

        # 'Farina,Rebecca' -- first and last are swapped in this one row
        if first == "Farina" and last == "Rebecca":
            first, last = "Rebecca", "Farina"

        name = fix_text(("%s %s" % (first, last)).strip())
        if name.startswith("Dejan Slep"):
            name = "Dejan Slepčev"
        slug = canon_slug(name)
        if not slug:
            continue

        position = fix_text(clean_text(row.get("Position")))
        affil1 = fix_text(clean_text(row.get("Affiliation1")))
        affil2 = fix_text(clean_text(row.get("Affiliation2")))
        rtype = ROSTER_TYPES.get((clean_text(row.get("Type")) or "").lower())

        rec = {"name": name, "roster": rtype}
        # Shubhanshu Shekhar has Position == Affiliation1 == "Assistant Professor";
        # keep the title, drop the duplicated non-institution.
        if affil1 and affil1 == position:
            affil1 = None
        # "Deceased" is not a job title.
        if position and position.lower() == "deceased":
            rec["memorial"] = True
            position = None

        if position:
            rec["position"] = position
        if affil1:
            rec["affiliation"] = affil1
        if affil2:
            rec["affiliation2"] = affil2
        url = clean_text(row.get("Webpage"))
        if url:
            rec["url"] = url if url.startswith("http") else "https://" + url.lstrip("/")
        img = clean_text(row.get("ImgPath"))
        if img and img.lower() != "none":
            # scripts/optimize_images.py re-encodes EVERYTHING to .jpg, so the
            # source extension (.png/.jpeg/.gif) must not survive into the path
            # or the photo 404s. This bit Balakrishnan, Jing Lei and Aarti Singh.
            stem = os.path.splitext(os.path.basename(img))[0]
            rec["img"] = "/assets/people/" + stem + ".jpg"
        people[slug] = rec

    apply_overrides(people)
    return people


def apply_overrides(people):
    """Layer people_overrides.yaml on top of the CSV.

    people.csv was last touched in Dec 2025 and has drifted (promotions,
    new members). Keeping corrections in their own file means re-running this
    migration cannot silently revert them.
    """
    path = os.path.join(HERE, "people_overrides.yaml")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        overrides = yaml.safe_load(fh) or {}
    for slug, patch in overrides.items():
        rec = people.setdefault(slug, {})
        for k, v in (patch or {}).items():
            if v is None:
                rec.pop(k, None)
            else:
                rec[k] = v
        people[slug] = rec


# --------------------------------------------------------------------------
# talks
# --------------------------------------------------------------------------

def load_json(name):
    with open(os.path.join("build", name), encoding="utf-8") as fh:
        return json.load(fh)


def build_talks(legacy_dir):
    idx = load_json("index.json")
    pages = load_json("pages.json")["pages"]
    csvs = load_json("csvs.json")["rows"]
    sheet = load_json("sheet.json")
    aarti = load_json("aarti.json")["talks"]

    # ---- index by (date, speaker_slug) ------------------------------------
    def key_of(date, raw):
        ss = speaker_slugs(raw)
        return (date, ss[0] if ss else None)

    page_by_url = {p["url"]: p for p in pages}
    page_by_key = {}
    for p in pages:
        page_by_key.setdefault(key_of(p["path_date"], p["speaker_raw"]), p)
    csv_by_key = {}
    for r in csvs:
        csv_by_key.setdefault(key_of(r["date"], r["speaker_raw"]), r)
    sheet_by_key = {}
    for e in sheet["entries"]:
        if e["kind"] == "talk":
            sheet_by_key.setdefault(key_of(e["date"], e["speaker_raw"]), e)
    aarti_by_key = {}
    for t in aarti:
        if t.get("speaker_raw"):
            aarti_by_key.setdefault(key_of(t["date"], t["speaker_raw"]), t)

    terms = OrderedDict()
    for t in idx["terms"]:
        terms[t["key"]] = {"key": t["key"], "name": t["name"], "talks": []}

    used_pages = set()
    seen_keys = set()

    # ---- 1. the spine: every entry in blog/index.html ----------------------
    for e in idx["entries"]:
        if e["kind"] == "placeholder":
            continue
        slugs = speaker_slugs(e["speaker_raw"])
        k = (e["date"], slugs[0] if slugs else None)
        seen_keys.add(k)

        page = None
        if e["href"] and not e["external"]:
            page = page_by_url.get(e["href"])
            if page is None:
                # the 3 known broken links -- resolve by (date, speaker)
                page = page_by_key.get(k)
        else:
            page = page_by_key.get(k)
        if page:
            used_pages.add(page["url"])

        row = csv_by_key.get(k)
        sh = sheet_by_key.get(k)
        aa = aarti_by_key.get(k)

        talk = assemble(e, page, row, sh, aa, terms)
        terms[e["term"]]["talks"].append(talk)

    # ---- 2. orphan pages: on disk, linked from nothing ---------------------
    # Dedupe by CONTENT, not by path. blog/2017/08/31/ryantibs.html is a
    # byte-identical copy of the 2017-05-03 Dave Choi talk filed under the wrong
    # date -- its (path_date, speaker) key is unique, so a path-based check
    # would happily admit it as a second, fictitious talk.
    content_seen = set()
    for t in terms.values():
        for talk in t["talks"]:
            content_seen.add(_content_key(talk.get("title"), talk.get("speakers")))

    for p in pages:
        if p["url"] in used_pages:
            continue
        slugs = speaker_slugs(p["speaker_raw"])
        k = (p["path_date"], slugs[0] if slugs else None)
        ck = _content_key(p.get("title"), slugs)
        if k in seen_keys or ck in content_seen:
            # same talk under a second filename -> emit a redirect, not a talk
            _attach_legacy_url(terms, ck, p["url"])
            log_conflict("duplicate_page", p["url"], "content-match",
                         p.get("title"), "page", "redirect only, not a second talk")
            continue
        seen_keys.add(k)
        content_seen.add(ck)
        term = infer_term(p["path_date"], terms)
        e = {"term": term, "date": p["path_date"], "title": p["title"],
             "speaker_raw": p["speaker_raw"], "href": p["url"],
             "date_note": None, "external": False, "kind": "talk"}
        talk = assemble(e, p, csv_by_key.get(k), sheet_by_key.get(k), aarti_by_key.get(k), terms)
        talk["recovered"] = "orphan page, linked from nowhere"
        terms[term]["talks"].append(talk)
        log_conflict("recovered_talk", p["url"], "page", p["title"], "index", "(absent)")

    # ---- 3. sheet-only semesters (Fall 2025, Spring 2026, Fall 2026) -------
    for e in sheet["entries"]:
        k = key_of(e["date"], e["speaker_raw"]) if e["kind"] == "talk" else (e["date"], None)
        if e["kind"] == "talk" and k in seen_keys:
            continue
        if e["term"] not in terms:
            terms[e["term"]] = {"key": e["term"], "name": e["term_name"], "talks": []}
        if e["kind"] == "talk":
            seen_keys.add(k)
        terms[e["term"]]["talks"].append(from_sheet(e))

    # ---- 4. pre-2015 enrichment: paper_url / paper_authors ----------------
    for t in aarti:
        if not t.get("speaker_raw"):
            continue
        k = key_of(t["date"], t["speaker_raw"])
        if k in seen_keys:
            continue
        seen_keys.add(k)
        term = t["term"]
        if term not in terms:
            terms[term] = {"key": term, "name": t["term_name"], "talks": []}
        terms[term]["talks"].append(from_aarti(t))
        log_conflict("recovered_talk", "%s %s" % (t["date"], t["speaker_raw"]),
                     "aarti", t.get("title"), "index", "(absent)")

    for t in terms.values():
        t["talks"].sort(key=lambda x: (x.get("date") or "", x.get("title") or ""))
    return terms, sheet["blocks"]


def _content_key(title, speakers):
    """Identity of a talk by what it SAYS, independent of where it is filed."""
    return (_title_norm(title or ""), tuple(sorted(speakers or [])))


def _attach_legacy_url(terms, content_key, url):
    """Point a duplicate filename at the talk it actually duplicates."""
    for t in terms.values():
        for talk in t["talks"]:
            if _content_key(talk.get("title"), talk.get("speakers")) == content_key:
                urls = set(talk.get("legacy_urls") or [])
                urls.update(both_paddings(url))
                talk["legacy_urls"] = sorted(urls)
                return True
    return False


def infer_term(date, terms):
    y, m = int(date[:4]), int(date[5:7])
    season = "spring" if m <= 6 else ("summer" if m == 7 else "fall")
    k = "%s%d" % (season, y)
    return k if k in terms else ("fall%d" % y if "fall%d" % y in terms else k)


def pick(field, key, *cands):
    """cands: (source_name, value). First non-empty wins; rest are logged."""
    chosen_src = chosen = None
    for src, val in cands:
        if val in (None, "", []):
            continue
        if chosen is None:
            chosen_src, chosen = src, val
        elif str(val).strip() != str(chosen).strip():
            log_conflict(field, key, chosen_src, chosen, src, val)
    return chosen


def _title_norm(s):
    """Casefold, strip accents and punctuation -- for equivalence, not display."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.casefold())


def pick_title(key, *cands):
    """Prefer the page's title, EXCEPT where another source is typographically richer.

    The archive index writes titles in sentence case; the pages use title case,
    so page-first is right 52 times out of 66. But the pages were hand-typed and
    sometimes lost diacritics the index kept -- 'Komlos-Major-Tusnady' on the
    page vs 'Komlós-Major-Tusnády' in the index. Among candidates that are the
    same title modulo case and accents, take the one carrying the most non-ASCII
    characters, then the longest (the CSVs truncate).
    """
    vals = [(src, clean_text(v)) for src, v in cands if v]
    if not vals:
        return None
    head_norm = _title_norm(vals[0][1])
    equiv = [(s, v) for s, v in vals if _title_norm(v) == head_norm]
    others = [(s, v) for s, v in vals if _title_norm(v) != head_norm]

    def richness(item):
        _, v = item
        return (sum(1 for c in v if ord(c) > 127), len(v))

    best_src, best = max(equiv, key=richness) if equiv else vals[0]
    for src, v in others:
        log_conflict("title", key, best_src, best, src, v)
    return best


def assemble(e, page, row, sh, aa, terms):
    key = "%s %s" % (e.get("date"), (e.get("speaker_raw") or "?"))

    # Compare SLUGS, not raw strings. "Prof. David Choi" vs "Dave Choi" is not a
    # conflict -- the alias map resolves both to david_choi. Logging raw-string
    # differences buried the 2 real disagreements under 26 false ones.
    cands = [("page", page and page.get("speaker_raw")),
             ("csv", row and row.get("speaker_raw")),
             ("index", e.get("speaker_raw")),
             ("sheet", sh and sh.get("speaker_raw"))]
    resolved = [(src, speaker_slugs(v)) for src, v in cands if v]
    speakers = resolved[0][1] if resolved else speaker_slugs(e.get("speaker_raw"))
    for src, slugs in resolved[1:]:
        if slugs and slugs != speakers:
            log_conflict("speaker", key, resolved[0][0], speakers, src, slugs)

    talk = {"date": e.get("date")}
    if e.get("date_note"):
        talk["date_note"] = e["date_note"]
    talk["speakers"] = speakers
    talk["title"] = pick_title(key,
                               ("page", page and page.get("title")),
                               ("index", e.get("title")),
                               ("csv", row and row.get("title")),
                               ("sheet", sh and sh.get("title")))
    abstract = pick("abstract", key,
                    ("page", page and page.get("abstract")),
                    ("csv", row and row.get("abstract")),
                    ("sheet", sh and sh.get("abstract")))
    if abstract:
        talk["abstract"] = abstract

    time = pick("time", key, ("csv", row and row.get("time")),
                ("page", page and page.get("time")), ("sheet", sh and sh.get("time")))
    room = pick("room", key, ("csv", row and row.get("room")),
                ("page", page and page.get("room")), ("sheet", sh and sh.get("room")))
    if time:
        talk["time"] = time
    if room:
        talk["room"] = room
    wd = (page and page.get("weekday")) or (sh and sh.get("weekday_override"))
    if wd:
        talk["weekday_override"] = wd

    paper = pick("paper_url", key, ("page", page and page.get("paper_url")),
                 ("aarti", aa and aa.get("paper_url")))
    if paper:
        talk["paper_url"] = paper
    if aa and aa.get("paper_authors"):
        talk["paper_authors"] = aa["paper_authors"]
    if page and page.get("latex"):
        talk["latex"] = page["latex"]

    urls = []
    if e.get("href") and not e.get("external"):
        urls.extend(both_paddings(e["href"]))
    if page and page["url"] not in urls:
        urls.extend(both_paddings(page["url"]))
    if e.get("external"):
        talk["external_url"] = e["href"]
    if urls:
        talk["legacy_urls"] = sorted(set(urls))

    srcs = [n for n, v in (("blog_index", e), ("blog_page", page),
                           ("csv", row), ("sheet", sh), ("aarti", aa)) if v]
    talk["sources"] = srcs
    return talk


def from_sheet(e):
    t = {"date": e["date"]}
    if e["kind"] != "talk":
        t["kind"] = e["kind"]
        if e.get("label"):
            t["label"] = e["label"]
    else:
        t["speakers"] = speaker_slugs(e["speaker_raw"])
        if e.get("title"):
            t["title"] = e["title"]
        if e.get("abstract"):
            t["abstract"] = e["abstract"]
    for k in ("room", "note"):
        if e.get(k):
            t[k] = e[k]
    if e.get("weekday_override"):
        t["weekday_override"] = e["weekday_override"]
    t["sources"] = ["sheet"]
    return t


def from_aarti(t):
    out = {"date": t["date"], "speakers": speaker_slugs(t["speaker_raw"])}
    for src, dst in (("title", "title"), ("paper_url", "paper_url"),
                     ("paper_authors", "paper_authors"), ("room", "room")):
        if t.get(src):
            out[dst] = t[src]
    if t.get("source_page", "").startswith("index_"):
        out["external_url"] = "https://www.cs.cmu.edu/~aarti/SMLRG/" + t["source_page"]
    out["sources"] = ["aarti"]
    return out


# --------------------------------------------------------------------------
# emit
# --------------------------------------------------------------------------

class Dumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper, data):
    if "\n" in data or len(data) > 110:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=">")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


Dumper.add_representer(str, _str_presenter)
Dumper.add_representer(OrderedDict,
                       lambda d, x: d.represent_mapping("tag:yaml.org,2002:map", x.items()))


def dump(path, obj, header):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header.rstrip() + "\n\n")
        yaml.dump(obj, fh, Dumper=Dumper, allow_unicode=True,
                  default_flow_style=False, sort_keys=False, width=96)


SEASON_ORDER = {"spring": 1, "summer": 2, "fall": 3}


def term_sort_key(key):
    m = re.match(r"(spring|summer|fall|winter)(\d{4})", key)
    if not m:
        return (0, 0)
    return (int(m.group(2)), SEASON_ORDER.get(m.group(1), 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", default=DEFAULT_LEGACY)
    ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "_data"))
    args = ap.parse_args()
    out = os.path.abspath(args.out)

    people = load_people(args.legacy)
    terms, blocks = build_talks(args.legacy)
    block_by_key = {b["key"]: b for b in blocks}

    # every speaker referenced by a talk must exist in people.yaml
    referenced = set()
    for t in terms.values():
        for talk in t["talks"]:
            referenced.update(talk.get("speakers") or [])
    # Overrides are applied inside load_people(), which runs BEFORE external
    # speakers are known. An override targeting someone who appears only as a
    # speaker therefore creates an entry with no `name`. Backfill by slug
    # rather than only creating wholly-absent people.
    for slug in sorted(referenced | set(people)):
        rec = people.setdefault(slug, {})
        if not rec.get("name"):
            rec["name"] = prettify(slug)

    # ---- terms.yaml
    # The "2009-2010" bucket holds only the archive's own "And there was once a
    # beginning!" placeholder, which is not a talk. Drop empty terms.
    for k in [k for k, t in terms.items() if not t["talks"]]:
        del terms[k]
    ordered = sorted(terms.values(), key=lambda t: term_sort_key(t["key"]), reverse=True)
    term_docs = []
    for t in ordered:
        b = block_by_key.get(t["key"], {})
        n_talks = sum(1 for x in t["talks"] if not x.get("kind"))
        d = OrderedDict([("key", t["key"]), ("name", t["name"]),
                         ("talks", n_talks)])
        if b.get("default_room"):
            d["default_room"] = b["default_room"]
        if b.get("default_time"):
            d["default_time"] = b["default_time"]
        if b.get("default_weekday"):
            d["default_weekday"] = b["default_weekday"]
        if b.get("note"):
            d["note"] = b["note"]
        term_docs.append(d)
    term_docs[0]["status"] = "upcoming"
    dump(os.path.join(out, "terms.yaml"), term_docs,
         "# Ordered newest-first. This order drives the archive.\n"
         "# `key` matches _data/talks/<key>.yaml. Generated by scripts/migrate/merge.py.")

    # ---- talks/<term>.yaml
    for t in ordered:
        dump(os.path.join(out, "talks", t["key"] + ".yaml"), t["talks"],
             "# %s -- %d entries. Generated by scripts/migrate/merge.py;\n"
             "# safe to hand-edit afterwards (the migration is one-shot)."
             % (t["name"], len(t["talks"])))

    # ---- people.yaml
    dump(os.path.join(out, "people.yaml"), dict(people),
         "# Every person the site names, keyed by slug.\n"
         "#   roster: present  -> group member, appears on /people/\n"
         "#   roster: absent   -> external speaker, appears only in talk bylines")

    # ---- roster.yaml
    roster = defaultdict(list)
    for slug, p in people.items():
        if p.get("roster"):
            roster[p["roster"]].append(slug)
    dump(os.path.join(out, "roster.yaml"),
         {k: sorted(v, key=lambda s: people[s]["name"].split()[-1])
          for k, v in roster.items()},
         "# Display order for /people/. Moving a student to alumni is one line.")

    # ---- conflicts
    with open("build/conflicts.tsv", "w", encoding="utf-8") as fh:
        fh.write("field\tkey\tchosen_source\tchosen\tother_source\tother\n")
        for c in CONFLICTS:
            fh.write("\t".join(c) + "\n")

    total = sum(len(t["talks"]) for t in ordered)
    real = sum(1 for t in ordered for x in t["talks"] if not x.get("kind"))
    print("terms     %d" % len(ordered))
    print("entries   %d  (talks %d, non-talk %d)" % (total, real, total - real))
    print("people    %d  (roster %d, external %d)" % (
        len(people), sum(1 for p in people.values() if p.get("roster")),
        sum(1 for p in people.values() if not p.get("roster"))))
    print("conflicts %d  -> build/conflicts.tsv" % len(CONFLICTS))
    print("wrote     %s" % out)


def prettify(slug):
    return " ".join(w.capitalize() for w in slug.split("_"))


if __name__ == "__main__":
    main()
