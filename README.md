# LinkedIn CLI monorepo

A local web login for the LinkedIn CLI. The browser app starts the existing CLI login flow, watches its progress, and reports when the LinkedIn session has been saved.

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

Click "Open LinkedIn in Chrome". A separate Chrome window opens because LinkedIn blocks its login page inside embedded frames. Finish login there. The web page will switch to "Connected" after the CLI saves the session.

## CLI

Run CLI commands from the monorepo root:

```bash
pnpm cli -- whoami
pnpm cli -- profile show williamhgates
```

The original command set remains under `apps/cli`.

## API

The local API exposes three endpoints:

```text
GET  /api/health
GET  /api/auth/status
POST /api/auth/login
```

`POST /api/auth/login` launches the existing `python apps/cli/main.py login` flow in a background thread. The status endpoint returns `idle`, `waiting`, `authenticated`, or `failed`.

## Checks

```bash
pnpm lint
pnpm build
pnpm test
```

The existing live LinkedIn integration tests remain in `apps/cli/tests`. They require a saved LinkedIn session and are not part of the default test command.
