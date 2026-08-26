import json
import os
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

from local_paths import local_data_dir


class LoginState(str, Enum):
    IDLE = "idle"
    WAITING = "waiting"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"


class LoginAlreadyRunning(Exception):
    pass


@dataclass(frozen=True)
class LoginSnapshot:
    status: LoginState
    message: str
    started_at: str | None
    updated_at: str

    def to_dict(self) -> dict[str, str | None]:
        values = asdict(self)
        values["status"] = self.status.value
        return values


PopenFactory = Callable[..., subprocess.Popen[str]]


class LoginManager:
    def __init__(
        self,
        cookies_file: Path | None = None,
        cli_entrypoint: Path | None = None,
        popen_factory: PopenFactory = subprocess.Popen,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        self.cookies_file = cookies_file or local_data_dir() / "cookies.json"
        self.cli_entrypoint = cli_entrypoint or Path(
            os.environ.get(
                "LINKEDIN_CLI_ENTRYPOINT",
                repo_root / "apps" / "cli" / "main.py",
            )
        )
        self.popen_factory = popen_factory
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None
        self._started_at: str | None = None
        initial_state = (
            LoginState.AUTHENTICATED if self._has_saved_session() else LoginState.IDLE
        )
        self._snapshot = self._make_snapshot(initial_state)

    def _has_saved_session(self) -> bool:
        if not self.cookies_file.exists():
            return False
        try:
            cookies = json.loads(self.cookies_file.read_text())
        except (json.JSONDecodeError, OSError):
            return False
        return isinstance(cookies, list) and any(
            isinstance(cookie, dict)
            and cookie.get("name") == "li_at"
            and bool(cookie.get("value"))
            for cookie in cookies
        )

    def _make_snapshot(self, state: LoginState) -> LoginSnapshot:
        messages = {
            LoginState.IDLE: "No LinkedIn session found on this Mac.",
            LoginState.WAITING: "Chrome is open. Finish signing in to LinkedIn.",
            LoginState.AUTHENTICATED: "LinkedIn session saved on this Mac.",
            LoginState.FAILED: "Login failed. Try opening LinkedIn again.",
        }
        return LoginSnapshot(
            status=state,
            message=messages[state],
            started_at=self._started_at,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    def status(self) -> LoginSnapshot:
        with self._lock:
            return self._snapshot

    def start(self) -> LoginSnapshot:
        with self._lock:
            if self._snapshot.status == LoginState.WAITING:
                raise LoginAlreadyRunning
            self._started_at = datetime.now(timezone.utc).isoformat()
            self._snapshot = self._make_snapshot(LoginState.WAITING)
            self._thread = threading.Thread(target=self._run, daemon=True)
            thread = self._thread

        thread.start()
        return self.status()

    def wait_for_completion(self, timeout: float = 5) -> LoginSnapshot:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        return self.status()

    def _run(self) -> None:
        try:
            command = (
                [sys.executable, "login"]
                if getattr(sys, "frozen", False)
                else [sys.executable, str(self.cli_entrypoint), "login"]
            )
            process = self.popen_factory(
                command,
                cwd=None if getattr(sys, "frozen", False) else self.cli_entrypoint.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            with self._lock:
                self._process = process
            process.communicate(timeout=330)
            state = (
                LoginState.AUTHENTICATED
                if process.returncode == 0 and self._has_saved_session()
                else LoginState.FAILED
            )
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            state = LoginState.FAILED
        except (OSError, ValueError):
            state = LoginState.FAILED

        with self._lock:
            self._process = None
            self._snapshot = self._make_snapshot(state)
