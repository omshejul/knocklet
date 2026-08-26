import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from login_api.cli_login import LoginManager, LoginState


class CompletedProcess:
    returncode = 0

    def __init__(self, cookies_file: Path):
        self.cookies_file = cookies_file

    def communicate(self, timeout=None):
        self.cookies_file.write_text(
            json.dumps([{"name": "li_at", "value": "saved"}])
        )
        return "Login successful!", None


class FailedProcess:
    returncode = 1

    def communicate(self, timeout=None):
        return "Exception: Failed to connect to browser", None


class LoginManagerTests(SimpleTestCase):
    def test_reports_existing_session(self):
        with TemporaryDirectory() as directory:
            cookies_file = Path(directory) / "cookies.json"
            cookies_file.write_text(
                json.dumps([{"name": "li_at", "value": "saved"}])
            )

            manager = LoginManager(cookies_file=cookies_file)

            assert manager.status().status == LoginState.AUTHENTICATED

    def test_login_process_updates_status(self):
        with TemporaryDirectory() as directory:
            cookies_file = Path(directory) / "cookies.json"
            cli_entrypoint = Path(directory) / "main.py"
            cli_entrypoint.write_text("")

            manager = LoginManager(
                cookies_file=cookies_file,
                cli_entrypoint=cli_entrypoint,
                popen_factory=lambda *args, **kwargs: CompletedProcess(cookies_file),
            )

            assert manager.start().status == LoginState.WAITING
            assert manager.wait_for_completion().status == LoginState.AUTHENTICATED

    def test_packaged_login_relaunches_the_runtime(self):
        with TemporaryDirectory() as directory:
            cookies_file = Path(directory) / "cookies.json"
            captured_command = None

            def start_process(command, **kwargs):
                nonlocal captured_command
                captured_command = command
                return CompletedProcess(cookies_file)

            manager = LoginManager(
                cookies_file=cookies_file,
                popen_factory=start_process,
            )
            with patch.object(sys, "frozen", True, create=True):
                manager.start()
                manager.wait_for_completion()

            assert captured_command == [sys.executable, "login"]

    def test_retries_a_transient_chrome_start_failure(self):
        with TemporaryDirectory() as directory:
            cookies_file = Path(directory) / "cookies.json"
            attempts = 0

            def start_process(*args, **kwargs):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    return FailedProcess()
                return CompletedProcess(cookies_file)

            manager = LoginManager(
                cookies_file=cookies_file,
                popen_factory=start_process,
            )

            manager.start()
            snapshot = manager.wait_for_completion()

            assert attempts == 2
            assert snapshot.status == LoginState.AUTHENTICATED

    def test_reports_the_chrome_start_failure(self):
        with TemporaryDirectory() as directory:
            manager = LoginManager(
                cookies_file=Path(directory) / "cookies.json",
                popen_factory=lambda *args, **kwargs: FailedProcess(),
            )

            manager.start()
            snapshot = manager.wait_for_completion()

            assert snapshot.status == LoginState.FAILED
            assert snapshot.message == (
                "Chrome failed to start its login session. Quit Chrome and try again."
            )
