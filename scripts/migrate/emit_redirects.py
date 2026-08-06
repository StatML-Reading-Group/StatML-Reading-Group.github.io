#!/usr/bin/env python3
"""_data/talks/*.yaml -> blog/**/*.html redirect stubs.

The old site published every talk at /blog/YYYY/MM/DD/name.html. The new one
renders the whole archive from YAML, so those URLs have no page behind them.

This walks the `legacy_urls` recorded on each talk during the migration and
writes a small stub at every one, pointing at that talk's anchor in the
archive. Reading the URLs out of the talk data (rather than keeping a separate
map) means the redirects can never drift from the content.

Two paddings per talk: scripts/make_blog.py built paths with unpadded
f'{dt.month}/{dt.day}' from 2022-10 onward, while the earlier tree is
zero-padded -- and blog/index.html links a mix of both. Emitting both forms is
a few hundred 500-byte files and removes a whole class of dead link.

These pay off if statml.cs.cmu.edu is ever repointed here with a
path-preserving redirect: an old inbound link then lands on its stub and
forwards to the right talk.

Usage:  python3 scripts/migrate/emit_redirects.py [--out .] [--clean]
"""

import argparse
import glob
import os
import shutil
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

STUB = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Redirecting&hellip;</title>
<link rel="canonical" href="{target}">
<meta http-equiv="refresh" content="0; url={target}">
<meta name="robots" content="noindex, follow">
<script>location.replace("{target}");</script>
</head>
<body>
<p>This talk has moved to <a href="{target}">{label}</a>.</p>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=ROOT)
    ap.add_argument("--clean", action="store_true",
                    help="remove the blog/ tree first")
    args = ap.parse_args()

    blog_dir = os.path.join(args.out, "blog")
    if args.clean and os.path.isdir(blog_dir):
        shutil.rmtree(blog_dir)

    terms = yaml.safe_load(open(os.path.join(args.out, "_data", "terms.yaml"),
                                encoding="utf-8"))
    term_name = {t["key"]: t["name"] for t in terms}

    written = 0
    talks_with_urls = 0
    for path in sorted(glob.glob(os.path.join(args.out, "_data", "talks", "*.yaml"))):
        key = os.path.splitext(os.path.basename(path))[0]
        for talk in yaml.safe_load(open(path, encoding="utf-8")) or []:
            urls = talk.get("legacy_urls") or []
            if not urls:
                continue
            talks_with_urls += 1

            speaker = (talk.get("speakers") or [None])[0]
            anchor = "t-%s%s" % (talk["date"], "-" + speaker if speaker else "")
            target = "/archive/#%s" % anchor
            label = "%s &mdash; %s" % (term_name.get(key, key),
                                       (talk.get("title") or "the archive"))

            for url in urls:
                dest = os.path.join(args.out, url.lstrip("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w", encoding="utf-8") as fh:
                    fh.write(STUB.format(target=target, label=label))
                written += 1

    print("talks carrying legacy URLs : %d" % talks_with_urls)
    print("stub files written         : %d" % written)
    print("output                     : %s" % blog_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
