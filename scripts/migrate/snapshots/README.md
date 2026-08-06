# Frozen migration inputs

These are **immutable snapshots** taken on **2026-08-06**. The migration parses *these files*,
never the live sources. Do not edit or refresh them.

## Why

Two of the three upstream sources are outside our control and are actively drifting:

- **The Google Sheet mutated mid-planning.** Two Fall 2025 date cells changed between two reads
  hours apart (`9/24/2025 (In NSH 4405)` → `9/24/2025 (ICLR)`, and `10/8/2025 (GHC 6115)` →
  `10/8/2025 (Gates 4405)`). Parsing the live sheet means the migration is not reproducible and you
  can never tell "the data changed" apart from "I mis-parsed it."
- **The pre-2015 pages live on a personal faculty directory** (`www.cs.cmu.edu/~aarti/SMLRG/`).
  They carry `paper_url` and `paper_authors` for 106 talks that exist **nowhere else** — not in our
  repo, not in the Sheet. When that directory goes away, so does the only copy.

## Contents

| Path | Source | Captured |
|---|---|---|
| `sheet-gid0-2026-08-06.csv` | [Schedule sheet](https://docs.google.com/spreadsheets/d/10-lexYyn9TEy9R5KZHv3qLNAfGO8ubRVTSQoEfqj05s), gid=0 | 2026-08-06 |
| `aarti-2026-08-06/*.html` | `https://www.cs.cmu.edu/~aarti/SMLRG/` — 9 pages, all HTTP 200 | 2026-08-06 |

`sheet-gid0-2026-08-06.csv` — 76,182 bytes, 139 CSV rows (297 *lines*; abstracts contain embedded
newlines, so always parse with `csv.reader`, never `splitlines()`).
SHA-256 `3eadc3a83b4d1563ac633de05a41759780e56a11ce46669632e36a31ee1af756`.

Eight schedule blocks, stacked in one tab: Fall 2026 (row 0), Spring 2026 (16), Fall 2025 (30),
Fall 2024 (48), Spring 2024 (69), Fall 2023 (88), Spring 2023 (109), Fall 2022 (127).
**Fall 2025 and Spring 2026 exist only here** — they were never archived to the site.

Per-file checksums for the aarti pages are in `aarti-2026-08-06/SHA256SUMS`.

## Verifying

```sh
shasum -a 256 -c SHA256SUMS
```
