from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from login_api.cli_login import LoginSnapshot, LoginState


def snapshot(state: LoginState) -> LoginSnapshot:
    return LoginSnapshot(
        status=state,
        message="test status",
        started_at=None,
        updated_at="2026-08-26T00:00:00+00:00",
    )


class LoginApiTests(TestCase):
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

    def test_lists_saved_imports(self):
        csv_file = SimpleUploadedFile(
            "people.csv",
            b"Name,LinkedIn URL\nAda Lovelace,https://linkedin.com/in/ada-lovelace\n",
            content_type="text/csv",
        )
        self.client.post("/api/connections/import", {"csv_file": csv_file})

        response = self.client.get("/api/connections/imports")

        assert response.status_code == 200
        assert response.json()[0]["filename"] == "people.csv"

    @patch("login_api.api.connection_imports")
    def test_approves_only_selected_connection_rows(self, store):
        store.approve.return_value = {
            "id": "import-id",
            "filename": "people.csv",
            "status": "checking",
            "people": [],
            "ready_count": 0,
            "sent_count": 0,
            "accepted_count": 0,
            "pending_count": 0,
            "connected_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "total_count": 2,
            "checked_count": 0,
            "processed_count": 0,
            "progress_percent": 0,
            "created_at": "2026-08-26T00:00:00+00:00",
            "approved_at": "2026-08-26T00:00:01+00:00",
            "completed_at": None,
        }

        response = self.client.post(
            "/api/connections/import/import-id/approve",
            data={"row_numbers": [2, 4]},
            content_type="application/json",
        )

        assert response.status_code == 202
        store.approve.assert_called_once_with("import-id", [2, 4])

    @patch("login_api.api.connection_imports")
    def test_refreshes_connection_acceptance(self, store):
        store.refresh_acceptance.return_value = {
            "checked_count": 2,
            "accepted_count": 1,
            "pending_count": 1,
            "checked_at": "2026-08-26T00:00:00+00:00",
        }

        response = self.client.post("/api/connections/acceptance/refresh")

        assert response.status_code == 200
        assert response.json()["accepted_count"] == 1
