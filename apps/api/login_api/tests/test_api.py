from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from login_api.cli_login import LoginSnapshot, LoginState
from login_api.models import Invitation, Message, MessageTemplate, Person, WorkItem


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

    def test_saves_message_template(self):
        response = self.client.put(
            "/api/message-template",
            data={
                "name": "Accepted",
                "body": "Thanks for connecting, {first_name}.",
                "auto_send_enabled": True,
            },
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.json()["auto_send_enabled"] is True
        assert response.json()["delay_minutes"] == 5
        assert self.client.get("/api/message-template").json()["name"] == "Accepted"

    def test_saving_reuses_the_only_message_template(self):
        first = self.client.put(
            "/api/message-template",
            data={
                "name": "First",
                "body": "Hello {first_name}",
                "delay_minutes": 15,
            },
            content_type="application/json",
        )
        second = self.client.put(
            "/api/message-template",
            data={
                "name": "Updated",
                "body": "Welcome {first_name}",
                "delay_minutes": 30,
            },
            content_type="application/json",
        )

        assert first.json()["id"] == second.json()["id"]
        assert second.json()["delay_minutes"] == 30
        assert MessageTemplate.objects.count() == 1

    def test_rejects_unknown_message_template_field(self):
        response = self.client.put(
            "/api/message-template",
            data={
                "body": "Thanks for connecting, {dummy_name}.",
                "auto_send_enabled": True,
            },
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Unknown message field: {dummy_name}."
        )

    def test_lists_available_message_template_fields(self):
        response = self.client.get("/api/message-template/fields")

        assert response.status_code == 200
        assert response.json() == [
            {
                "name": "first_name",
                "label": "First name",
                "placeholder": "{first_name}",
            },
            {
                "name": "full_name",
                "label": "Full name",
                "placeholder": "{full_name}",
            },
        ]

    def test_reads_exact_work_item_status(self):
        work_item = WorkItem.objects.create(
            kind=WorkItem.Kind.CHECK_ACCEPTANCES,
            due_at=timezone.now(),
        )

        response = self.client.get(f"/api/automation/work/{work_item.id}")

        assert response.status_code == 200
        assert response.json()["id"] == str(work_item.id)
        assert response.json()["status"] == "queued"

    def test_lists_persisted_work_logs_with_exact_failure(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(person=person)
        work_item = WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_INVITATION,
            status=WorkItem.Status.FAILED,
            invitation=invitation,
            due_at=timezone.now(),
            attempt_count=1,
            error="LinkedIn returned status 429.",
            provider_status=429,
            completed_at=timezone.now(),
        )

        response = self.client.get("/api/logs")

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": str(work_item.id),
                "kind": "send_invitation",
                "status": "failed",
                "person_name": "Ada Lovelace",
                "error": "LinkedIn returned status 429.",
                "provider_status": 429,
                "attempt_count": 1,
                "activity_at": work_item.completed_at.isoformat(),
                "due_at": work_item.due_at.isoformat(),
                "created_at": work_item.created_at.isoformat(),
                "started_at": None,
                "completed_at": work_item.completed_at.isoformat(),
            }
        ]

    def test_processes_only_safe_people_actions(self):
        not_started = Person.objects.create(name="Not started", public_id="new")
        failed = Person.objects.create(name="Failed", public_id="failed")
        failed_invitation = Invitation.objects.create(
            person=failed,
            status=Invitation.Status.FAILED,
            error="LinkedIn returned status 429.",
        )
        pending = Person.objects.create(name="Pending", public_id="pending")
        Invitation.objects.create(
            person=pending,
            status=Invitation.Status.PENDING,
            sent_at=timezone.now(),
        )
        accepted = Person.objects.create(name="Accepted", public_id="accepted")
        accepted_invitation = Invitation.objects.create(
            person=accepted,
            status=Invitation.Status.ACCEPTED,
        )
        failed_message = Message.objects.create(
            invitation=accepted_invitation,
            body="Hello",
            status=Message.Status.FAILED,
            error="LinkedIn returned status 500.",
        )
        review = Person.objects.create(name="Review", public_id="review")
        review_invitation = Invitation.objects.create(
            person=review,
            status=Invitation.Status.NEEDS_REVIEW,
        )

        response = self.client.post(
            "/api/people/process",
            data={
                "person_ids": [
                    str(not_started.id),
                    str(failed.id),
                    str(pending.id),
                    str(accepted.id),
                    str(review.id),
                ]
            },
            content_type="application/json",
        )

        assert response.status_code == 202
        result = response.json()
        assert result == {
            "requested_count": 5,
            "invitation_count": 2,
            "message_count": 1,
            "check_count": 1,
            "skipped_count": 1,
            "acceptance_work_item_id": result["acceptance_work_item_id"],
        }
        assert result["acceptance_work_item_id"] is not None
        failed_invitation.refresh_from_db()
        failed_message.refresh_from_db()
        review_invitation.refresh_from_db()
        assert failed_invitation.status == Invitation.Status.QUEUED
        assert failed_message.status == Message.Status.QUEUED
        assert review_invitation.status == Invitation.Status.NEEDS_REVIEW
        assert WorkItem.objects.filter(kind=WorkItem.Kind.SEND_INVITATION).count() == 2
        assert WorkItem.objects.filter(kind=WorkItem.Kind.SEND_MESSAGE).count() == 1
        assert WorkItem.objects.filter(kind=WorkItem.Kind.CHECK_ACCEPTANCES).count() == 1

        second_response = self.client.post(
            "/api/people/process",
            data={"person_ids": [str(not_started.id), str(failed.id), str(accepted.id)]},
            content_type="application/json",
        )

        assert second_response.status_code == 202
        assert second_response.json()["skipped_count"] == 3
        assert WorkItem.objects.filter(kind=WorkItem.Kind.SEND_INVITATION).count() == 2
        assert WorkItem.objects.filter(kind=WorkItem.Kind.SEND_MESSAGE).count() == 1

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

    @patch("login_api.api.enqueue_acceptance_check")
    def test_requests_connection_acceptance_check(self, enqueue):
        enqueue.return_value = None
        response = self.client.post("/api/connections/acceptance/refresh")

        assert response.status_code == 200
        assert response.json()["state"] == "no_pending"
        enqueue.assert_called_once_with(force=True)

    def test_deletes_person_and_local_outreach_records(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(person=person)
        message = Message.objects.create(invitation=invitation, body="Hello Ada")
        WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_MESSAGE,
            invitation=invitation,
            message=message,
            due_at=timezone.now(),
        )

        response = self.client.delete(f"/api/people/{person.id}")

        assert response.status_code == 204
        assert not Person.objects.filter(pk=person.id).exists()
        assert not Invitation.objects.filter(pk=invitation.id).exists()
        assert not Message.objects.filter(pk=message.id).exists()
        assert not WorkItem.objects.filter(message_id=message.id).exists()

    def test_rejects_person_delete_while_their_action_is_running(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(person=person)
        WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_INVITATION,
            status=WorkItem.Status.RUNNING,
            invitation=invitation,
            due_at=timezone.now(),
        )

        response = self.client.delete(f"/api/people/{person.id}")

        assert response.status_code == 409
        assert response.json() == {
            "detail": "Wait for the current action to finish."
        }
        assert Person.objects.filter(pk=person.id).exists()

    def test_returns_not_found_when_deleting_unknown_person(self):
        response = self.client.delete("/api/people/not-a-person")

        assert response.status_code == 404
        assert response.json() == {"detail": "Person not found."}
