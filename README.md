# StatML Reading Group — website

Source for **https://statml-reading-group.github.io/**

Built with Jekyll and deployed by GitHub Pages on every push to `master`.
**There is no server to log into.**

## A short history, because it explains the design

Until July 2025 the site lived at `statml.cs.cmu.edu`, served out of
`/afs/andrew.cmu.edu/usr13/aramdas/statml` and deployed by someone SSH-ing in
and running `git pull`. That summer CMU SCS stopped serving Andrew-cell AFS
content from its web hosts. The site went dark and stayed dark for thirteen
months — two commits were pushed after the cutoff and went nowhere, because the
person pushing had no way to know the deploy target no longer existed.

Everything below follows from not wanting that to happen again: no server, no
manual deploy step, no dependency on any one person's account or directory.

## How to change things

Almost every change is a YAML edit. You do not need to touch HTML.

| To do this | Edit this |
|---|---|
| Add or update a talk | `_data/talks/<term>.yaml` |
| Start a new semester | add to `_data/terms.yaml`, create `_data/talks/<key>.yaml` |
| Add or correct a person | `_data/people.yaml` |
| Move someone student → alumni | change their `roster:` in `_data/people.yaml` |
| Change who organizes | `_data/organizers.yaml` |

Push to `master`; the site rebuilds in about two minutes.

### Adding a talk

```yaml
- date: 2026-09-14                       # ISO. Quote it or leave it bare — never MM/DD.
  speakers: [ben_chugg]                  # slugs from _data/people.yaml. A list: talks can have two.
  title: "Post-hoc asymptotic inference"
  abstract: >-
    Optional. Renders in the collapsible dropdown on the archive page.
  room: GHC 8228                         # only if it differs from the term default
  time: "11:00am-12:00pm"                # ditto
```

Non-talk rows use `kind:` instead of `speakers`/`title`:

```yaml
- date: 2026-11-26
  kind: no_meeting        # no_meeting | cancelled | tbd
  label: Thanksgiving
```

These show on the homepage while the term is running and are filtered out of
the archive, which lists only talks that happened.

### Adding a person

```yaml
jane_doe:
  name: Jane Doe
  roster: student         # faculty | postdoc | student | alumni
  position: Graduate Student
  affiliation: Statistics & Data Science
  url: https://example.com          # omit if they have none — never guess
  img: /assets/people/jane-doe.jpg  # faculty only; see below
```

Someone **without** a `roster:` is an external speaker: they get a byline on
their talk but do not appear on the People page.

Only **faculty** photos are displayed. If you add one, run
`python3 scripts/optimize_images.py` before committing — the old site shipped
27 MB of headshots to render them at 160×200 px.

## Local preview

```sh
bundle install
bundle exec jekyll serve --livereload      # http://localhost:4000
```

## Layout

```
index.html archive.html people.html history.html   the four pages
_layouts/default.html                              the only layout
_includes/talk.html  person.html  nav.html         reused components
_data/                                             ALL content lives here
libs/custom/my_css.css  site.js                    design system
assets/people/                                     93 optimized headshots
blog/                                              generated redirect stubs (see below)
scripts/migrate/                                   one-shot migration, kept for provenance
```

### `blog/` is generated — do not hand-edit

410 stub files preserving the old site's talk URLs. Regenerate with:

```sh
python3 scripts/migrate/emit_redirects.py --clean
```

They are built from the `legacy_urls` recorded on each talk, so they cannot
drift from the content. Two paths exist per talk because the old generator
wrote unpadded months (`/blog/2025/4/25/`) while the earlier tree was padded
(`/blog/2025/04/25/`), and the old index linked a mix of both.

### `scripts/migrate/` is archival

The one-shot scripts that reconstructed 352 talks from five sources: the old
archive index, 223 hand-written talk pages, six schedule CSVs, the Google
Sheet, and the pre-2015 pages Aarti Singh hosted. **Not part of the build.**

Kept because `scripts/migrate/snapshots/` holds frozen copies of two sources
that are outside our control and were already drifting — the schedule Sheet
changed twice during the migration itself, and the pre-2015 pages live on a
personal faculty directory that will eventually disappear. They carry paper
links for 106 talks that exist nowhere else.

`_data/*.yaml` is the source of truth now. Edit it directly; re-running the
migration is not part of any normal workflow.

## Conventions

- **Never publish an unverified affiliation.** Leave the field blank instead.
  These are real people. `scripts/migrate/people_overrides.yaml` records what
  was verified and what deliberately was not.
- **Watch for links that return 200 but are stale.** Several old CMU pages
  still resolve while showing a years-old student bio — a link checker will not
  catch those.
- **Never create a repo named `statml-website` in this org.** GitHub's redirect
  from the old name would break.

## Maintaining this repo

Owned by the **StatML-Reading-Group** organization, not by any individual — it
survives everyone graduating.

- **Handing over:** Settings → People → add the incoming organizer as **Owner**,
  remove those who have left. Any owner can do this.
- **Keep at least two owners** so no single departure strands the org.
- **Update the org's billing email** when the current holder leaves, or
  notifications go to a dead address. This is the org-level version of the AFS
  problem that killed the last site.

### Related repos

- `StatML-Reading-Group/statml-dev` — private working copy
- `StatML-Reading-Group/statml-website-archive` — the pre-2026 site, frozen,
  tagged `pre-revamp-2026-08-06`

### Optional: reclaiming `statml.cs.cmu.edu`

The name still resolves; CMU SCS simply de-provisioned the vhost. Reclaiming it
needs a ticket to SCS (with Aaditya Ramdas as historical owner) asking them to
CNAME it here, or failing that a path-preserving 301. The `blog/` stubs are
what make a path-preserving redirect actually work.
