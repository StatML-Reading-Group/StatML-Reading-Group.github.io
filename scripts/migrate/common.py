"""Shared primitives for the one-shot content migration.

Three hazards live in here, each of which silently corrupts data if you skip it.
They are documented at their implementations:

  read_text()   -- 7 source files are CP1252, not UTF-8
  slugify()     -- NFKD *deletes* the letters in "Varıcı" and "Chwiałkowski"
  meta_text()   -- <p class="meta"> is never closed in 157 of the blog pages

Python 3.9 compatible (no match, no dict |, no zoneinfo).
"""

import html
import os
import re
import unicodedata
from datetime import datetime

from bs4 import NavigableString

# --------------------------------------------------------------------------
# Encoding
# --------------------------------------------------------------------------

# These 7 files are Windows-1252, not UTF-8, despite every one of them
# declaring <meta charset="utf-8">. They render as mojibake on the live site
# today, and they would hard-fail the Jekyll build the moment front matter is
# added (Liquid parses them; a static copy does not).
KNOWN_CP1252 = {
    "assets/spring2025.csv",
    "assets/fall2024.csv",
    "blog/2020/03/03/yuting.html",
    "blog/2024/10/22/michael.html",
    "blog/2024/11/12/diego.html",
    "blog/2025/2/21/tomas.html",
    "blog/2025/4/25/ziqi.html",
}


def read_text(path):
    """Decode a source file, falling back to CP1252. Returns (text, encoding)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        # cp1252 maps every byte 0x80-0x9f that latin-1 leaves undefined, which
        # is exactly the range these files use (0x92 ', 0x97 -, 0xa0 NBSP).
        return raw.decode("cp1252"), "cp1252"


# U+2019 ' and friends are fine to keep -- they are legitimate typography once
# the file is actually UTF-8. We only normalise the ones that break layout or
# comparison.
_WS_FIXES = {
    "\xa0": " ",   # NBSP -- collapses inconsistently in HTML, breaks == on titles
    " ": " ",  # line separator
    " ": " ",  # paragraph separator
    "﻿": "",   # BOM
}


def clean_text(s):
    """Normalise whitespace and decode HTML entities. Safe to call twice."""
    if s is None:
        return None
    s = html.unescape(s)
    # people.csv contains "Slep&#269ev" -- a numeric entity missing its
    # terminating semicolon, which html.unescape() handles but which no
    # stricter parser would. &#269; is U+010D LATIN SMALL LETTER C WITH CARON.
    for bad, good in _WS_FIXES.items():
        s = s.replace(bad, good)
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------
# Slugs and names
# --------------------------------------------------------------------------

# NFKD decomposes an accented letter into base + combining mark, so stripping
# the marks leaves the base letter. But a handful of Latin letters are NOT
# accented forms -- they are distinct letters with no decomposition at all.
# NFKD leaves them intact, and the subsequent ascii-encode DELETES them:
#
#   'Burak Varıcı'        -> 'burak_varc'         (ı U+0131 vanishes twice)
#   'Kacper Chwiałkowski' -> 'kacper_chwiakowski' (ł U+0142 vanishes)
#
# Both are real speakers. Map them to their conventional ASCII equivalents
# BEFORE normalising.
_PRE_ASCII = str.maketrans({
    "ı": "i", "İ": "I",
    "ł": "l", "Ł": "L",
    "ø": "o", "Ø": "O",
    "đ": "d", "Đ": "D",
    "ħ": "h", "Ħ": "H",
    "ß": "ss",
    "æ": "ae", "Æ": "AE",
    "œ": "oe", "Œ": "OE",
    "þ": "th", "Þ": "TH",
    "ð": "d", "Ð": "D",
})


def slugify(name):
    """'Prof. José Chacón (Extremadura)' -> 'jose_chacon'."""
    s = clean_text(name)
    if not s:
        return None
    s = strip_affiliation(s)
    s = re.sub(r"^(prof|dr|professor)\.?\s+", "", s, flags=re.I)
    s = s.translate(_PRE_ASCII)
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s or None


def strip_affiliation(s):
    """Drop a trailing '(UW Madison)' or ', Rutgers' from a speaker string.

    Only strips parentheticals that look like an affiliation. Scheduling notes
    ('(3--4pm to accommodate Fienberg lecture)', '(Wednesday)') are left alone
    for split_speaker_note() to pull out separately.
    """
    s = s.strip()
    # Always drop a TRAILING parenthetical from the name. Whether it was an
    # affiliation or a scheduling note only decides where its content is
    # routed (see split_speaker_note) -- either way it is not part of the name.
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()
    # ", University of Cambridge" / ", The Florida State University" / ", ETH Zurich".
    # The institution word may lead OR trail, so match either side of the comma.
    s = re.sub(
        r",\s*(?:the\s+)?[^,]*\b"
        r"(?:University|Universite|Universidad|College|Institute|Institut|School|"
        r"Academy|Laborator(?:y|ies)|Labs?|Research|Inc\.?|Ltd\.?|Corp\.?|"
        r"ETH|EPFL|MIT|CMU|INRIA)\b.*$",
        "", s, flags=re.I).strip()
    return s.rstrip(",").strip()


def _looks_like_scheduling(inner):
    """True if a parenthetical is about WHEN/WHERE, not WHO."""
    t = inner.lower()
    if re.search(r"\d", t):          # times, room numbers, dates
        return True
    if re.search(r"\b(am|pm|joint|seminar|no meeting|cancel|break|moved|note)\b", t):
        return True
    if t.strip() in WEEKDAYS_LOWER:
        return True
    return False


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAYS_LOWER = {d.lower() for d in WEEKDAYS}

ROOM_RE = re.compile(
    r"\b((?:GHC|NSH|BH|WEH|POS|DH|SH|Gates|Baker|Wean|Porter|Doherty|Scaife|Hamerschlag|Newell[- ]Simon)"
    r"[\s-]*[\dA-Z]{3,5})\b",
    re.I,
)


def split_speaker_note(cell):
    """Pull affiliation / room / weekday / free-note out of a speaker cell.

    Returns dict with keys: name, affiliation, room, weekday, note (any may be None).
    """
    out = {"name": None, "affiliation": None, "room": None, "weekday": None, "note": None}
    s = clean_text(cell)
    if not s:
        return out
    for inner in re.findall(r"\(([^)]*)\)", s):
        if inner.strip().lower() in WEEKDAYS_LOWER:
            out["weekday"] = inner.strip().title()
        elif ROOM_RE.search(inner):
            out["room"] = clean_text(ROOM_RE.search(inner).group(1))
        elif _looks_like_scheduling(inner):
            out["note"] = clean_text(inner)
        else:
            out["affiliation"] = clean_text(inner)
    out["name"] = strip_affiliation(s)
    return out


def split_speakers(raw):
    """One speaker cell -> list of individual names.

    Real multi-presenter entries exist ('Darren Homrighausen and Dan McDonald',
    Fall 2012), so `speakers` is a LIST throughout the schema. Splitting on
    'and' is only safe once affiliations are stripped -- 'Institute for
    Computing and Information Sciences' would otherwise split.
    """
    s = clean_text(raw)
    if not s:
        return []
    s = strip_affiliation(s)
    parts = re.split(r"\s*(?:,|;|&|\band\b)\s*", s)
    out = []
    for p in parts:
        p = p.strip()
        # a bare initial or a fragment is not a name
        if len(p) < 3 or not re.search(r"[A-Za-z]{2,}\s+[A-Za-z]", p):
            continue
        out.append(p)
    return out or ([s] if s else [])


# --------------------------------------------------------------------------
# Non-talk rows
# --------------------------------------------------------------------------

_NO_MEETING = re.compile(
    r"\b(no\s*meeting|no\s*class|fall\s*break|spring\s*break|thanksgiving|"
    r"democracy\s*day|holiday|winter\s*break|recess)\b", re.I)
_CANCELLED = re.compile(r"\bcancel", re.I)
_TBD = re.compile(r"^\s*(tbd|tba|n/?a)\s*$", re.I)


# The reason a meeting didn't happen, as opposed to the bare phrase "no meeting".
_BREAK_NAME = re.compile(
    r"\b(fall\s*break|spring\s*break|winter\s*break|thanksgiving|democracy\s*day|"
    r"holiday|recess)\b", re.I)
_NO_MEETING_PHRASE = re.compile(
    r"\b(no\s*meetings?|no\s*class|cancell?ed)\b[\s:.\-–—]*", re.I)


def classify_row(speaker_cell):
    """-> (kind, label). kind is 'talk' | 'no_meeting' | 'cancelled' | 'tbd'.

    The label is the REASON, preferred over the bare phrase:
        'No meeting (Thanksgiving)'   -> 'Thanksgiving'
        'Democracy Day (no meeting)'  -> 'Democracy Day'
        'NO MEETING -- FALL BREAK'    -> 'Fall Break'
        'No meeting'                  -> 'No meeting'
    """
    s = clean_text(speaker_cell) or ""
    if not s or _TBD.match(s):
        return "tbd", None

    named = _BREAK_NAME.search(s)
    label = clean_text(named.group(1)).title() if named else None

    if _CANCELLED.search(s):
        return "cancelled", label or clean_text(s)
    if _NO_MEETING.search(s):
        if not label:
            # strip the "no meeting" phrase and any brackets; keep what remains
            rest = _NO_MEETING_PHRASE.sub("", s)
            rest = clean_text(re.sub(r"[()\[\]]", " ", rest)).strip(" -–—:.")
            label = rest or clean_text(s)
        return "no_meeting", label
    return "talk", None


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

_DATE_FORMATS = [
    "%d %b %Y",     # 25 Apr 2025          blog/index.html (299 entries)
    "%d %B %Y",     # 28 October 2015      blog/index.html (30 entries)
    "%d %b, %Y",    # 12 Nov, 2024         shape-C page meta
    "%b %d, %Y",    # Nov 12, 2024
    "%B %d, %Y",
    "%m/%d/%Y",     # 10/25/2022           assets/*.csv
    "%m/%d/%y",
    "%Y-%m-%d",
]

# No year -- caller supplies it. BOTH orders are present in the corpus:
# "Nov 18" (shape-B page metas) and "22 Feb" (the Spring 2017 two-part entry).
# Omitting the day-first forms silently mis-dates that talk by a week.
_MONTH_DAY_FORMATS = ["%b %d", "%B %d", "%d %b", "%d %B", "%m/%d"]


# strptime's %b accepts exactly the 3-letter abbreviations. The pre-2015 pages
# write "Sept 1" and "Sept 22", which fail silently and drop every September
# talk on a page. Normalise the long-ish forms before parsing.
_MONTH_ALIASES = [
    (r"\bSept\.?\b", "Sep"), (r"\bSep\b", "Sep"),
    (r"\bJune\b", "Jun"), (r"\bJuly\b", "Jul"),
    (r"\bMarch\b", "Mar"), (r"\bApril\b", "Apr"),
    (r"\bAug\.?\b", "Aug"), (r"\bOct\.?\b", "Oct"),
    (r"\bNov\.?\b", "Nov"), (r"\bDec\.?\b", "Dec"),
    (r"\bJan\.?\b", "Jan"), (r"\bFeb\.?\b", "Feb"),
]


def _normalize_month(s):
    for pat, repl in _MONTH_ALIASES:
        s = re.sub(pat, repl, s, flags=re.I)
    return s


def parse_date(text, fallback_year=None):
    """Parse any date form seen in the corpus. Returns datetime.date or None.

    127 of 223 blog page metas carry NO year -- always pass fallback_year from
    the file path or the semester, never trust the meta to be self-contained.
    """
    s = clean_text(text)
    if not s:
        return None
    # strip trailing scheduling parentheticals: "9/5 (Thursday) - NSH 4305"
    s = re.sub(r"\s*[-–]\s*.*$", "", s)
    s = re.sub(r"\s*\([^)]*\)", "", s).strip().rstrip(",")
    s = _normalize_month(s)

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    if fallback_year:
        for fmt in _MONTH_DAY_FORMATS:
            try:
                return datetime.strptime(s, fmt).replace(year=fallback_year).date()
            except ValueError:
                pass
    # Last resort: a leading "Mon DD" or "M/D" inside a longer meta string.
    # Guard against recursing on an unchanged string -- when the fragment IS
    # the whole input, recursion never terminates.
    m = re.match(r"([A-Za-z]{3,9}\.?\s+\d{1,2}|\d{1,2}/\d{1,2})", s)
    if m and fallback_year:
        frag = m.group(1).strip()
        if frag and frag != s:
            return parse_date(frag, fallback_year)
    return None


def parse_date_multi(text, fallback_year=None):
    """Handle two-part talks: '22 Feb and 01 Mar 2017' -> (date, note).

    Exactly one entry in the corpus has this shape (Sangwon Hyun, Spring 2017,
    a talk given over two consecutive weeks). Anchor on the FIRST date and
    carry the second as a note; the year lives only on the trailing part.
    """
    s = clean_text(text)
    if not s:
        return None, None
    parts = re.split(r"\s+(?:and|&|\+)\s+", s)
    if len(parts) < 2:
        return parse_date(s, fallback_year), None
    tail = parse_date(parts[-1], fallback_year)
    year = tail.year if tail else fallback_year
    head = parse_date(parts[0], year)
    if head and tail:
        return head, "continued %s" % tail.strftime("%b %-d")
    return (head or tail), None


def parse_date_cell(cell, fallback_year=None):
    """Sheet date cells embed room/day overrides. -> dict(date, weekday, room, note)."""
    out = {"date": None, "weekday": None, "room": None, "note": None}
    s = clean_text(cell)
    if not s:
        return out
    for inner in re.findall(r"\(([^)]*)\)", s):
        if inner.strip().lower() in WEEKDAYS_LOWER:
            out["weekday"] = inner.strip().title()
        elif ROOM_RE.search(inner):
            out["room"] = clean_text(ROOM_RE.search(inner).group(1))
        else:
            out["note"] = clean_text(inner)
    tail = re.split(r"\s*[-–]\s*", re.sub(r"\s*\([^)]*\)", "", s))
    if len(tail) > 1 and ROOM_RE.search(tail[1]):
        out["room"] = clean_text(ROOM_RE.search(tail[1]).group(1))
    out["date"] = parse_date(s, fallback_year)
    return out


def check_weekday(date, claimed):
    """A stated weekday that disagrees with the date means a wrong year or day."""
    if not (date and claimed):
        return True
    return date.strftime("%A").lower() == claimed.strip().lower()


# --------------------------------------------------------------------------
# Terms
# --------------------------------------------------------------------------

def term_key(name):
    """'Fall 2010' -> 'fall2010'.  '2009-2010' -> '2009_2010'."""
    s = clean_text(name).lower()
    m = re.match(r"(fall|spring|summer|winter)\s+(\d{4})", s)
    if m:
        return "%s%s" % (m.group(1), m.group(2))
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


# --------------------------------------------------------------------------
# HTML extraction
# --------------------------------------------------------------------------

# <p class="meta"> is never closed in the 157 pre-2023 pages. html.parser
# therefore nests the ENTIRE remainder of the document -- post body, footer,
# nav, everything -- inside the <p>, so meta.get_text() returns the whole page.
#
# Walk direct children only and stop at the first block-level child, which is
# where the real <p> would have ended.
_BLEED_STOP = {"div", "h1", "h2", "h3", "h4", "h5", "h6", "p", "footer", "script"}


def meta_text(meta_tag):
    """Text of a <p class="meta">, immune to the unclosed-tag bleed."""
    parts = []
    for child in meta_tag.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif child.name == "br":
            parts.append(" ")
        elif child.name in _BLEED_STOP:
            break
        else:
            parts.append(child.get_text(" "))
    return clean_text(" ".join(parts))


def rel_path(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def both_paddings(url):
    """/blog/2025/4/25/x.html -> both the padded and unpadded forms.

    scripts/make_blog.py built paths with unpadded f'{dt.month}/{dt.day}',
    while the pre-2023 tree is zero-padded. Emit redirects for both so a link
    written either way resolves.
    """
    m = re.match(r"^(/blog)/(\d{4})/(\d{1,2})/(\d{1,2})/(.+)$", url)
    if not m:
        return [url]
    pre, y, mo, d, tail = m.groups()
    forms = {
        "%s/%s/%s/%s/%s" % (pre, y, mo.zfill(2), d.zfill(2), tail),
        "%s/%s/%s/%s/%s" % (pre, y, str(int(mo)), str(int(d)), tail),
    }
    return sorted(forms)
