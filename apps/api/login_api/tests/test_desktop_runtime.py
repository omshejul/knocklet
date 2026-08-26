import os
from unittest.mock import patch

from django.test import SimpleTestCase

from desktop_runtime import main


class DesktopRuntimeTests(SimpleTestCase):
    @patch("desktop_runtime.execute_from_command_line")
    def test_migrate_runs_without_prompts(self, execute):
        main(["migrate"])

        execute.assert_called_once_with(
            ["knocklet-runtime", "migrate", "--noinput"]
        )

    @patch("desktop_runtime.execute_from_command_line")
    def test_serve_uses_configured_address(self, execute):
        with patch.dict(os.environ, {"KNOCKLET_API_ADDRESS": "127.0.0.1:49000"}):
            main(["serve"])

        execute.assert_called_once_with(
            ["knocklet-runtime", "runserver", "127.0.0.1:49000", "--noreload"]
        )

    def test_unknown_mode_fails_explicitly(self):
        with self.assertRaisesMessage(SystemExit, "Unknown Knocklet runtime mode: nope"):
            main(["nope"])
