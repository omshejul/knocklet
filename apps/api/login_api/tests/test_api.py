from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from login_api.cli_login import LoginSnapshot, LoginState
from login_api.models import (
    ConnectionImport,
    ConnectionRequest,
    Invitation,
    Message,
    MessageTemplate,
    Person,
    WorkItem,
)


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
        assert response.json() == {
            "items": [
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
            ],
            "has_more": False,
            "next_offset": None,
        }

    def test_paginates_and_filters_work_logs(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(person=person)
        now = timezone.now()
        for index in range(3):
            WorkItem.objects.create(
                kind=WorkItem.Kind.SEND_INVITATION,
                status=WorkItem.Status.FAILED,
                invitation=invitation,
                due_at=now - timedelta(minutes=index),
                error=f"Failure {index}",
                completed_at=now - timedelta(minutes=index),
            )
        WorkItem.objects.create(
            kind=WorkItem.Kind.CHECK_ACCEPTANCES,
            status=WorkItem.Status.SUCCEEDED,
            due_at=now,
            completed_at=now,
        )

        first_response = self.client.get(
            "/api/logs?limit=2&offset=0&status=failed&kind=send_invitation&search=Ada"
        )
        second_response = self.client.get(
            "/api/logs?limit=2&offset=2&status=failed&kind=send_invitation&search=Ada"
        )

        assert first_response.status_code == 200
        assert [item["error"] for item in first_response.json()["items"]] == [
            "Failure 0",
            "Failure 1",
        ]
        assert first_response.json()["has_more"] is True
        assert first_response.json()["next_offset"] == 2
        assert [item["error"] for item in second_response.json()["items"]] == [
            "Failure 2"
        ]
        assert second_response.json()["has_more"] is False
        assert second_response.json()["next_offset"] is None

    def test_rejects_invalid_log_page(self):
        responses = [
            self.client.get("/api/logs?limit=0&offset=-1"),
            self.client.get("/api/logs?limit=1001"),
        ]

        for response in responses:
            assert response.status_code == 400
            assert response.json() == {
                "detail": (
                    "Log offset must be zero or greater and limit must be between 1 and 1000."
                )
            }

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

    def test_people_include_the_inferred_first_name(self):
        Person.objects.create(name="CA Akhil Kumar", public_id="akhil")

        response = self.client.get("/api/people")

        assert response.status_code == 200
        assert response.json()[0]["first_name"] == "Akhil"

    def test_updates_first_name_used_by_new_messages(self):
        person = Person.objects.create(name="CA Akhil Kumar", public_id="akhil")
        Invitation.objects.create(
            person=person,
            status=Invitation.Status.ACCEPTED,
        )
        MessageTemplate.objects.create(
            body="Hello {first_name}",
            is_active=True,
        )

        response = self.client.patch(
            f"/api/people/{person.id}",
            data={"first_name": " Akhilendra "},
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.json() == {
            "id": str(person.id),
            "first_name": "Akhilendra",
        }
        person.refresh_from_db()
        assert person.first_name == "Akhilendra"

        queue_response = self.client.post(
            "/api/people/messages",
            data={"person_ids": [str(person.id)]},
            content_type="application/json",
        )

        assert queue_response.status_code == 202, queue_response.json()
        assert Message.objects.get(invitation__person=person).body == (
            "Hello Akhilendra"
        )

    def test_rejects_a_blank_first_name(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")

        response = self.client.patch(
            f"/api/people/{person.id}",
            data={"first_name": "   "},
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "First name is required."}

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

    def test_queues_a_message_for_an_accepted_person_without_one(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.ACCEPTED,
            accepted_at=timezone.now(),
        )
        MessageTemplate.objects.create(
            body="Hello {first_name}",
            is_active=True,
        )

        response = self.client.post(
            "/api/people/messages",
            data={"person_ids": [str(person.id)]},
            content_type="application/json",
        )

        assert response.status_code == 202
        assert response.json() == {"queued_count": 1}
        message = Message.objects.get(invitation=invitation)
        assert message.body == "Hello Ada"
        assert message.status == Message.Status.QUEUED
        assert WorkItem.objects.filter(
            kind=WorkItem.Kind.SEND_MESSAGE,
            message=message,
            status=WorkItem.Status.QUEUED,
        ).count() == 1

    def test_retries_a_failed_message_without_creating_another(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.ACCEPTED,
            accepted_at=timezone.now(),
        )
        message = Message.objects.create(
            invitation=invitation,
            body="Hello Ada",
            status=Message.Status.FAILED,
            error="LinkedIn returned status 429.",
        )
        work_item = WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_MESSAGE,
            status=WorkItem.Status.FAILED,
            invitation=invitation,
            message=message,
            due_at=timezone.now(),
            error=message.error,
            completed_at=timezone.now(),
            dedupe_key=f"message:{message.id}",
        )

        response = self.client.post(
            "/api/people/messages",
            data={"person_ids": [str(person.id)]},
            content_type="application/json",
        )

        assert response.status_code == 202
        message.refresh_from_db()
        work_item.refresh_from_db()
        assert message.status == Message.Status.QUEUED
        assert message.error == ""
        assert work_item.status == WorkItem.Status.QUEUED
        assert work_item.error == ""
        assert work_item.completed_at is None
        assert Message.objects.filter(invitation=invitation).count() == 1
        assert WorkItem.objects.filter(message=message).count() == 1

    def test_retries_a_failed_invitation(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        completed_at = timezone.now()
        connection_import = ConnectionImport.objects.create(
            filename="people.csv",
            status=ConnectionImport.Status.COMPLETE,
            completed_at=completed_at,
        )
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.FAILED,
            error="LinkedIn returned status 429.",
        )
        connection_request = ConnectionRequest.objects.create(
            connection_import=connection_import,
            row_number=2,
            name=person.name,
            public_id=person.public_id,
            status=ConnectionRequest.Status.FAILED,
            person=person,
            invitation=invitation,
        )
        work_item = WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_INVITATION,
            status=WorkItem.Status.FAILED,
            invitation=invitation,
            due_at=timezone.now(),
            error=invitation.error,
            completed_at=timezone.now(),
        )

        response = self.client.post(
            f"/api/people/{person.id}/invitation/retry",
        )

        assert response.status_code == 202
        assert response.json() == {"kind": "invitation", "status": "queued"}
        connection_import.refresh_from_db()
        connection_request.refresh_from_db()
        invitation.refresh_from_db()
        work_item.refresh_from_db()
        assert connection_import.status == ConnectionImport.Status.CHECKING
        assert connection_import.completed_at is None
        assert connection_request.status == ConnectionRequest.Status.READY
        assert invitation.status == Invitation.Status.QUEUED
        assert invitation.error == ""
        assert work_item.status == WorkItem.Status.QUEUED
        assert work_item.error == ""
        assert work_item.completed_at is None

    def test_confirms_an_uncertain_invitation_was_sent(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.NEEDS_REVIEW,
            error="LinkedIn did not confirm the invitation.",
        )
        started_at = timezone.now()
        work_item = WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_INVITATION,
            status=WorkItem.Status.NEEDS_REVIEW,
            invitation=invitation,
            due_at=started_at,
            started_at=started_at,
            completed_at=started_at,
            error=invitation.error,
        )

        response = self.client.post(
            f"/api/people/{person.id}/review",
            data={"outcome": "sent"},
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.json() == {"kind": "invitation", "status": "pending"}
        invitation.refresh_from_db()
        work_item.refresh_from_db()
        assert invitation.status == Invitation.Status.PENDING
        assert invitation.sent_at == started_at
        assert work_item.status == WorkItem.Status.SUCCEEDED

    def test_retries_an_uncertain_message_after_it_was_not_sent(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.ACCEPTED,
        )
        message = Message.objects.create(
            invitation=invitation,
            body="Hello Ada",
            status=Message.Status.NEEDS_REVIEW,
            error="LinkedIn did not confirm the message.",
        )
        work_item = WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_MESSAGE,
            status=WorkItem.Status.NEEDS_REVIEW,
            invitation=invitation,
            message=message,
            due_at=timezone.now(),
            completed_at=timezone.now(),
            error=message.error,
        )

        response = self.client.post(
            f"/api/people/{person.id}/review",
            data={"outcome": "not_sent"},
            content_type="application/json",
        )

        assert response.status_code == 202
        assert response.json() == {"kind": "message", "status": "queued"}
        message.refresh_from_db()
        work_item.refresh_from_db()
        assert message.status == Message.Status.QUEUED
        assert message.error == ""
        assert work_item.status == WorkItem.Status.QUEUED
        assert work_item.completed_at is None

    def test_resolves_an_interrupted_message_before_a_stale_invitation_review(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.NEEDS_REVIEW,
            error="The app stopped while this action was running.",
        )
        message = Message.objects.create(
            invitation=invitation,
            body="Hello Ada",
            status=Message.Status.NEEDS_REVIEW,
            error="LinkedIn did not confirm the message.",
        )
        started_at = timezone.now()
        work_item = WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_MESSAGE,
            status=WorkItem.Status.NEEDS_REVIEW,
            invitation=invitation,
            message=message,
            due_at=started_at,
            started_at=started_at,
            completed_at=started_at,
            error=message.error,
        )

        response = self.client.post(
            f"/api/people/{person.id}/review",
            data={"outcome": "sent"},
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.json() == {"kind": "message", "status": "sent"}
        invitation.refresh_from_db()
        message.refresh_from_db()
        work_item.refresh_from_db()
        assert invitation.status == Invitation.Status.ACCEPTED
        assert invitation.error == ""
        assert message.status == Message.Status.SENT
        assert message.sent_at == started_at
        assert work_item.status == WorkItem.Status.SUCCEEDED

    def test_retry_rebuilds_a_message_with_an_unresolved_field(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.ACCEPTED,
            accepted_at=timezone.now(),
        )
        template = MessageTemplate.objects.create(
            body="Hello {first_name}",
            is_active=True,
        )
        message = Message.objects.create(
            invitation=invitation,
            body="Hello {unknown_name}",
            status=Message.Status.FAILED,
            error="Message contains an unresolved field and was not sent.",
        )
        WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_MESSAGE,
            status=WorkItem.Status.FAILED,
            invitation=invitation,
            message=message,
            due_at=timezone.now(),
            error=message.error,
            completed_at=timezone.now(),
            dedupe_key=f"message:{message.id}",
        )

        response = self.client.post(
            "/api/people/messages",
            data={"person_ids": [str(person.id)]},
            content_type="application/json",
        )

        assert response.status_code == 202
        message.refresh_from_db()
        assert message.body == "Hello Ada"
        assert message.template == template
        assert message.status == Message.Status.QUEUED

    def test_rejects_a_message_for_a_person_who_is_not_accepted(self):
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        Invitation.objects.create(person=person, status=Invitation.Status.PENDING)
        MessageTemplate.objects.create(body="Hello", is_active=True)

        response = self.client.post(
            "/api/people/messages",
            data={"person_ids": [str(person.id)]},
            content_type="application/json",
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "Messages can only be sent to accepted connections."
        }

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
