from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from login_api.cli_login import LoginSnapshot, LoginState


def snapshot(state: LoginState) -> LoginSnapshot:
    return LoginSnapshot(
        status=state,
        message="test status",
        started_at=None,
        updated_at="2026-08-26T00:00:00+00:00",
    )


class LoginApiTests(SimpleTestCase):
    def test_health(self):
        response = self.client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @patch("login_api.api.login_manager")
    def test_starts_login(self, manager):
        manager.start.return_value = snapshot(LoginState.WAITING)

        response = self.client.post("/api/auth/login")

        assert response.status_code == 202
        assert response.json()["status"] == "waiting"

    def test_imports_clay_csv_for_preview(self):
        csv_file = SimpleUploadedFile(
            "people.csv",
            b"Name,LinkedIn URL\nAda Lovelace,https://linkedin.com/in/ada-lovelace\n",
            content_type="text/csv",
        )

        response = self.client.post(
            "/api/connections/import",
            {"csv_file": csv_file},
        )

        assert response.status_code == 201
        assert response.json()["ready_count"] == 1
        assert response.json()["people"][0]["name"] == "Ada Lovelace"
