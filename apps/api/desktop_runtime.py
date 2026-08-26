import os
import sys
from collections.abc import Sequence

from django.core.management import execute_from_command_line


def main(arguments: Sequence[str] | None = None) -> None:
    args = list(arguments if arguments is not None else sys.argv[1:])
    if len(args) != 1:
        raise SystemExit("Usage: knocklet-runtime <migrate|serve|worker|login>")

    mode = args[0]
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "linkedin_api.settings")

    if mode == "login":
        from auth import browser_login

        browser_login()
        return

    management_commands = {
        "migrate": ["migrate", "--noinput"],
        "serve": [
            "runserver",
            os.environ.get("KNOCKLET_API_ADDRESS", "127.0.0.1:47138"),
            "--noreload",
        ],
        "worker": ["run_local_worker"],
    }
    command = management_commands.get(mode)
    if command is None:
        raise SystemExit(f"Unknown Knocklet runtime mode: {mode}")
    execute_from_command_line(["knocklet-runtime", *command])


if __name__ == "__main__":
    main()
