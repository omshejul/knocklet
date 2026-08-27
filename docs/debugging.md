# Debugging

Start with persisted state, then trace the owner of the failing step. The screen is a view of API and SQLite state, not proof that a LinkedIn write happened.

## Evidence order

1. Read the exact UI error and Logs entry.
2. Inspect the related person, invitation, message, and `WorkItem` in SQLite.
3. Compare queued, started, completed, attempt, provider status, and error fields.
4. Inspect the CLI response only after the local state transition is understood.

The development database and cookies default to `~/.linkedin-cli`. A packaged app stores them under Electron's `userData` directory and writes runtime output to `userData/logs/desktop.log`.

## Common boundaries

- Login opens a separate Google Chrome session. It is not the Electron window or the user's normal embedded web view.
- The API queues work. The worker is required for queued invitations, acceptance checks, and messages to progress.
- A failed state is safe to retry after fixing its cause. A `needs_review` state is uncertain and requires checking LinkedIn first.
- Automatic messaging eligibility comes from the import approval snapshot. Enabling a template later does not schedule older accepted people.
- Development success does not prove the packaged PyInstaller runtime contains the same imports and files. Reproduce packaging failures with the packaged runtime.

Use fake LinkedIn clients and temporary data directories for tests. Live sends are reserved for an explicitly named test account and explicit user approval.
