# LinkedIn CLI monorepo

A local web interface for the LinkedIn CLI. It supports browser login and reviewed CSV batches for connection requests.

The session cookie stays in `~/.linkedin-cli/cookies.json`. The API never returns cookie values to the frontend.

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

Imports are limited to 100 non-empty rows and 2 MB. Their progress is kept in memory, so restarting the API clears the current batch.

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
GET  /api/connections/import/{id}
POST /api/connections/import/{id}/approve
```

`POST /api/auth/login` launches the existing `python apps/cli/main.py login` flow in a background thread. The status endpoint returns `idle`, `waiting`, `authenticated`, or `failed`.

The import endpoint only parses and previews the CSV. Requests start only after the approve endpoint is called. They are sent sequentially through the existing CLI client.

## Checks

```bash
pnpm lint
pnpm build
pnpm test
```

The existing live LinkedIn integration tests remain in `apps/cli/tests`. They require a saved LinkedIn session and are not part of the default test command.
