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
tag="v${version}"
replaced_tag="v0.1.0"
app_path="apps/desktop/dist/mac-arm64/Knocklet.app"
dmg_path="apps/desktop/dist/Knocklet-${version}-arm64.dmg"
zip_path="apps/desktop/dist/Knocklet-${version}-arm64.zip"
latest_path="apps/desktop/dist/latest-mac.yml"

visibility=$(gh repo view --json visibility --jq '.visibility')
if [[ "$visibility" != "PUBLIC" ]]; then
  echo "Release refused: public update downloads require a public repository." >&2
  exit 1
fi

if gh release view "$tag" >/dev/null 2>&1; then
  echo "Release refused: ${tag} already exists." >&2
  exit 1
fi

pnpm build:desktop

artifacts=(
  "$dmg_path"
  "$zip_path"
  "${zip_path}.blockmap"
)
for artifact in "${artifacts[@]}"; do
  if [[ ! -f "$artifact" ]]; then
    echo "Release refused: missing OTA artifact ${artifact}." >&2
    exit 1
  fi
done

codesign --verify --deep --strict --verbose=2 "$app_path"
codesign -dv --verbose=4 "$app_path" 2>&1 | rg "Authority=Developer ID Application|Timestamp=|flags=.*runtime"
signing_identity=$(
  codesign -dv --verbose=4 "$app_path" 2>&1 |
    sed -n 's/^Authority=\(Developer ID Application:.*\)$/\1/p' |
    head -n 1
)
if [[ -z "$signing_identity" ]]; then
  echo "Release refused: the app has no Developer ID Application identity." >&2
  exit 1
fi
codesign --force --timestamp --sign "$signing_identity" "$dmg_path"
codesign --verify --strict --verbose=2 "$dmg_path"

ASC_UPLOAD_TIMEOUT=10m asc notarization submit \
  --file "$dmg_path" \
  --wait \
  --timeout 1h \
  --output table

ASC_UPLOAD_TIMEOUT=10m asc notarization submit \
  --file "$zip_path" \
  --wait \
  --timeout 1h \
  --output table

xcrun stapler staple "$app_path"
xcrun stapler validate "$app_path"
xcrun stapler staple "$dmg_path"
xcrun stapler validate "$dmg_path"
spctl --assess --type execute --verbose=4 "$app_path"
spctl --assess --type open --context context:primary-signature --verbose=4 "$dmg_path"
shasum -a 256 "$dmg_path"
shasum -a 256 "$zip_path"

node apps/desktop/scripts/write-update-metadata.cjs \
  "$zip_path" \
  "$latest_path" \
  "$version"
artifacts+=("$latest_path")

gh release create "$tag" "${artifacts[@]}" \
  --target "$(git rev-parse HEAD)" \
  --title "Knocklet ${version}" \
  --notes "Fixes LinkedIn invitation and message delivery for profiles returned by search, and improves endpoint fallback safety." \
  --latest

published_assets=$(gh release view "$tag" --json assets --jq '.assets[].name')
for artifact in "${artifacts[@]}"; do
  name=$(basename "$artifact")
  if ! grep -Fxq "$name" <<<"$published_assets"; then
    echo "Release incomplete: ${name} was not published. The previous release was kept." >&2
    exit 1
  fi
done

if [[ "$tag" != "$replaced_tag" ]] && gh release view "$replaced_tag" >/dev/null 2>&1; then
  gh release delete "$replaced_tag" --cleanup-tag --yes
fi
