#!/bin/zsh

set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

git fetch origin main

if [[ -n $(git status --porcelain) ]]; then
  echo "Release refused: the worktree is not clean." >&2
  exit 1
fi

if [[ $(git rev-parse HEAD) != $(git rev-parse origin/main) ]]; then
  echo "Release refused: HEAD does not match origin/main." >&2
  exit 1
fi

version=$(node -p "require('./apps/desktop/package.json').version")
app_path="apps/desktop/dist/mac-arm64/Knocklet.app"
dmg_path="apps/desktop/dist/Knocklet-${version}-arm64.dmg"

pnpm build:desktop

codesign --verify --deep --strict --verbose=2 "$app_path"
codesign -dv --verbose=4 "$app_path" 2>&1 | rg "Authority=Developer ID Application|Timestamp=|flags=.*runtime"

ASC_UPLOAD_TIMEOUT=10m asc notarization submit \
  --file "$dmg_path" \
  --wait \
  --timeout 1h \
  --output table

xcrun stapler staple "$dmg_path"
xcrun stapler validate "$dmg_path"
spctl --assess --type open --context context:primary-signature --verbose=4 "$dmg_path"
shasum -a 256 "$dmg_path"
