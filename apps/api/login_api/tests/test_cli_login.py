import json
from pathlib import Path
from tempfile import TemporaryDirectory

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
