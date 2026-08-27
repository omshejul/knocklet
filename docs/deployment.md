# Deployment

Desktop releases come only from a fresh, clean checkout whose `HEAD` exactly matches `origin/main`. Merge and push every change before release work starts.

## Release model

- The version in `apps/desktop/package.json` defines the Git tag and artifact names.
- The build combines the exported Next.js app, a PyInstaller API and worker runtime, and the Electron shell.
- Developer ID signs the app and DMG. Apple notarizes both the DMG and OTA ZIP. The app and DMG receive stapled tickets and must pass Gatekeeper.
- GitHub Releases is the public OTA source. A release needs the arm64 ZIP, ZIP blockmap, and `latest-mac.yml`; the DMG is the manual installer.
- `latest-mac.yml` must describe the published ZIP with its final size and SHA-512 hash.

## Credentials

The Developer ID identity and `asc` authentication live in the macOS Keychain. Keep private keys, tokens, certificates, and notarization credentials out of Git and release artifacts. Use ignored environment files only for temporary local overrides.

## Completion

A release is done when Apple accepts both submissions, staple and Gatekeeper checks pass, the Git tag targets `origin/main`, every expected asset is uploaded, and GitHub reports that version as the latest release. Existing clients should then resolve the published update metadata without authentication.
