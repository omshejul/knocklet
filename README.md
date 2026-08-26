# LinkedIn CLI monorepo

A local web interface for the LinkedIn CLI. It supports browser login, reviewed CSV batches, and invitation history.

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

After login, choose a Clay CSV and click "Preview CSV". The importer accepts a `LinkedIn URL`, `LinkedIn Profile URL`, or `LinkedIn` column. Names can come from `Name`, `Full Name`, or separate `First Name` and `Last Name` columns. Review every row, then use the send button to approve the valid requests.

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
```

`POST /api/auth/login` launches the existing `python apps/cli/main.py login` flow in a background thread. The status endpoint returns `idle`, `waiting`, `authenticated`, or `failed`.

The import endpoint only parses and previews the CSV. Requests start only after the approve endpoint is called. Preflight checks run first, then eligible requests are sent sequentially through the existing CLI client.

## Checks

```bash
pnpm lint
pnpm build
pnpm test
```

The existing live LinkedIn integration tests remain in `apps/cli/tests`. They require a saved LinkedIn session and are not part of the default test command.
