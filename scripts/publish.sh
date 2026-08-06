#!/bin/sh
# Build, check, and publish the site.
#
#   ./scripts/publish.sh            check only -- does not push
#   ./scripts/publish.sh --push     check, then push (deploys in ~2 min)
#
# The same checks run again in CI, so a mistake cannot reach the site either
# way. Running them here just means finding out in 5 seconds instead of 90.

set -e
cd "$(dirname "$0")/.."

red()  { printf '\033[31m%s\033[0m\n' "$1"; }
ok()   { printf '\033[32m%s\033[0m\n' "$1"; }
fail() { red "FAIL: $1"; exit 1; }

echo "Building..."
bundle exec jekyll build --quiet

talks=$(grep -o 'class="talk"'         _site/archive/index.html | wc -l | tr -d ' ')
people=$(grep -o 'class="person-name"' _site/people/index.html  | wc -l | tr -d ' ')
stubs=$(find _site/blog -name '*.html' | wc -l | tr -d ' ')

# A renamed data key or a broken filter renders these EMPTY while the build
# still succeeds. That is the failure worth catching.
[ "$talks"  -ge 340 ] || fail "archive has $talks talks, expected >= 340"
[ "$people" -ge 90  ] || fail "people page has $people entries, expected >= 90"
[ "$stubs"  -ge 400 ] || fail "only $stubs redirect stubs, expected >= 400"
echo "  talks=$talks  people=$people  redirect stubs=$stubs"

echo "Checking links..."
# No --log-level: passing it makes html-proofer exit 1 even when all checks pass.
bundle exec htmlproofer ./_site \
  --disable-external --check-internal-hash --allow-hash-href \
  --no-enforce-https --ignore-files "/_site/blog/" 2>&1 \
  | grep -vi 'warning: IO::Buffer' || true

ok "All checks passed."

[ "$1" = "--push" ] || { echo "Not pushing. Re-run with --push to publish."; exit 0; }

[ -z "$(git status --porcelain)" ] || fail "uncommitted changes -- commit them first"

echo "Pushing..."
git push origin main
ok "Pushed. Live in ~2 minutes at https://statml-reading-group.github.io/"
echo "Watch:  gh run watch -R StatML-Reading-Group/StatML-Reading-Group.github.io"
