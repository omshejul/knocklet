# Knocklet

Knocklet is a local LinkedIn outreach app. It supports browser login, reviewed file imports, invitation history, and follow-up messages.

The session cookie stays in `~/.linkedin-cli/cookies.json`. Invitation data stays in a local SQLite database. The API never returns cookie values to the frontend.

## Repository layout

```text
apps/
  api/    Django Ninja API that controls the login process
  cli/    Existing Python CLI and browser automation
  web/    Next.js browser interface
packages/
  linkedin-cli-reference/
  linkedin-commander/
```

## Run locally

You need Google Chrome, Node.js 20.9 or newer, pnpm, uv, and Python 3.11 or newer.

```bash
pnpm install
uv sync --all-packages
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000). The API runs on `http://127.0.0.1:8000` and stays bound to localhost.

Click "Log in with LinkedIn". A separate Chrome window opens because LinkedIn blocks its login page inside embedded frames. Finish login there.

After login, choose a CSV, XLS, XLSX, XLSB, XLSM, or ODS file and click "Preview file". The importer detects the LinkedIn profile URL column from its header or `linkedin.com/in/` values. Names can come from `Name`, `Full Name`, or separate `First Name` and `Last Name` columns. Review every row, then use the send button to approve the valid requests.

Approval first loads sent invitations and checks each remaining profile. Pending invitations and existing connections are skipped. Only confirmed non-connections are sent, with visible checking and sending progress.

Imports are limited to 100 non-empty rows and 2 MB. Imports, people, send results, and acceptance checks survive API and app restarts.

## Local data

The database defaults to `~/.linkedin-cli/linkedin.sqlite3`. Set either variable before starting the app to use another local location:

```bash
LINKEDIN_DATA_DIR=/path/to/app-data pnpm dev
LINKEDIN_DATABASE_PATH=/path/to/linkedin.sqlite3 pnpm dev
```

`pnpm dev` runs database migrations before starting the API. A packaged Electron app can run `pnpm db:migrate` before launching its local API process.

The History table records who received a request, whether sending failed, and whether a sent invitation later became a first-degree connection. "Check accepted" reads recent LinkedIn connections and saves the result locally.

## CLI

Run CLI commands from the monorepo root:

```bash
pnpm cli -- whoami
pnpm cli -- profile show williamhgates
```

The original command set remains under `apps/cli`.

## API

The local API exposes these endpoints:

```text
GET  /api/health
GET  /api/auth/status
POST /api/auth/login
POST /api/connections/import
GET  /api/connections/imports
GET  /api/connections/import/{id}
POST /api/connections/import/{id}/approve
POST /api/connections/acceptance/refresh
GET  /api/people
DELETE /api/people/{id}
```

`POST /api/auth/login` launches the existing `python apps/cli/main.py login` flow in a background thread. The status endpoint returns `idle`, `waiting`, `authenticated`, or `failed`.

The import endpoint only parses and previews the CSV. Requests start only after the approve endpoint is called. Preflight checks run first, then eligible requests are sent sequentially through the existing CLI client.

## Checks

```bash
pnpm lint
pnpm build
pnpm test
```

## Desktop updates

The installed macOS app checks GitHub Releases on launch and every six hours. The sidebar and menu-bar menu can also check manually. A found update is downloaded only after the user approves it, then installed when the user chooses "Restart to update".

Run `pnpm release:desktop` from a clean checkout of GitHub `main` to build, sign, notarize, and publish the DMG, ZIP, blockmaps, and `latest-mac.yml`. The release command refuses private repositories because shipped apps must not contain a GitHub access token. It publishes the OTA-capable release before deleting `v0.1.0`.

Version `0.2.0` is the OTA baseline and needs one manual installation. Releases after it can update from inside Knocklet.

The existing live LinkedIn integration tests remain in `apps/cli/tests`. They require a saved LinkedIn session and are not part of the default test command.
