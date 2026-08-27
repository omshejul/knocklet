# Architecture

Knocklet is a local-first Electron app. SQLite is the durable source of truth. Browser storage is not used for outreach state.

## Boundaries

- `apps/web` renders the interface and calls the local API. It never calls LinkedIn directly.
- `apps/api` owns validation, people, imports, templates, statuses, SQLite, and durable work items.
- `apps/cli` owns Chrome login and LinkedIn requests.
- `apps/desktop` starts the packaged API, worker, and static web app, then manages the window, menu bar, and updates.
- `apps/site` is the public download page and has no access to local app data.

## Write path

The UI asks the API to create work. The API commits a `WorkItem` before returning. The worker performs the LinkedIn call and records the exact result. The UI polls the API for that persisted state.

## Invariants

- Importing previews the whole file, but approval processes only the selected rows.
- Invitation preflight skips an existing pending request or connection before sending.
- Automatic follow-ups use the template body and delay captured when that import was approved. Later template edits do not rewrite that approval.
- Manual sends use the current template. A failed retry keeps its original text unless that text contains an unresolved field.
- `needs_review` means an external write may have succeeded. Check LinkedIn and record an outcome before retrying.
- Deleting a person removes local automation state. It does not undo anything on LinkedIn.
