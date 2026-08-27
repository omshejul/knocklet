from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone

from login_api.automation import (
    ACCEPTANCE_INTERVAL,
    enqueue_acceptance_check,
    queue_messages_for_people,
    recover_interrupted_work,
    run_due_work,
)
from login_api.connection_imports import ConnectionImportStore
from login_api.models import (
    ConnectionImport,
    ConnectionRequest,
    Invitation,
    Message,
    MessageTemplate,
    Person,
    WorkItem,
)


class SafeClient:
    def __init__(self):
        self.sent = []
        self.sent_urns = []

    def get_sent_invitation_public_ids(self):
        return set()

    def get_connection_state(self, public_id, name=""):
        return {
            "state": "not_connected",
            "public_id": public_id,
            "url": f"https://www.linkedin.com/in/{public_id}/",
            "urn_id": f"urn:li:fsd_profile:{public_id}-id",
        }

    def add_connection(self, profile_public_id, profile_urn=None):
        self.sent.append(profile_public_id)
        self.sent_urns.append(profile_urn)
        return {"status": 201}


class UncertainClient(SafeClient):
    def add_connection(self, profile_public_id, profile_urn=None):
        raise TimeoutError("LinkedIn did not confirm the invitation.")


class RenamedProfileClient(SafeClient):
    def get_connection_state(self, public_id, name=""):
        return {
            "state": "not_connected",
            "public_id": "ca-tejas-kandoi-linked-in",
            "url": "https://www.linkedin.com/in/ca-tejas-kandoi-linked-in/",
            "urn_id": "urn:li:fsd_profile:tejas-id",
        }


class AcceptedMessagingClient:
    def __init__(self):
        self.messages = []
        self.since_ms = []

    def get_recent_connections(self, max_results, since_ms):
        self.since_ms.append(since_ms)
        return [{"public_id": "ada", "connected_at": since_ms + 1000}]

    def get_profile_urn(self, public_id):
        return "urn:li:fsd_profile:ada"

    def send_message(self, message_body, recipients):
        self.messages.append((message_body, recipients))
        return {"status": 201}


class AutomationTests(TransactionTestCase):
    def test_approval_only_queues_durable_work(self):
        client = SafeClient()
        store = ConnectionImportStore(client_factory=lambda: client)
        connection_import = store.create(
            b"Name,LinkedIn URL\nAda,https://linkedin.com/in/ada\n",
            "people.csv",
        )

        store.approve(connection_import["id"])

        assert client.sent == []
        assert WorkItem.objects.get(kind="send_invitation").status == "queued"
        run_due_work(lambda: client)
        assert client.sent == ["ada"]
        assert client.sent_urns == ["urn:li:fsd_profile:ada-id"]

    def test_renamed_profile_uses_and_saves_the_canonical_url(self):
        client = RenamedProfileClient()
        person = Person.objects.create(
            name="CA Tejas Kandoi",
            linkedin_url=(
                "https://www.linkedin.com/in/ca-tejas-kandoi-0b7b3476/"
            ),
            public_id="ca-tejas-kandoi-0b7b3476",
        )
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.QUEUED,
        )
        WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_INVITATION,
            invitation=invitation,
            due_at=timezone.now(),
        )

        run_due_work(lambda: client)

        person.refresh_from_db()
        assert client.sent == ["ca-tejas-kandoi-linked-in"]
        assert client.sent_urns == ["urn:li:fsd_profile:tejas-id"]
        assert person.public_id == "ca-tejas-kandoi-linked-in"
        assert person.normalized_public_id == "ca-tejas-kandoi-linked-in"
        assert person.linkedin_url == (
            "https://www.linkedin.com/in/ca-tejas-kandoi-linked-in/"
        )

    def test_uncertain_write_is_not_retried(self):
        store = ConnectionImportStore(client_factory=UncertainClient)
        connection_import = store.create(
            b"Name,LinkedIn URL\nAda,https://linkedin.com/in/ada\n",
            "people.csv",
        )
        store.approve(connection_import["id"])

        run_due_work(UncertainClient)

        assert Invitation.objects.get().status == "needs_review"
        assert WorkItem.objects.get(kind="send_invitation").status == "needs_review"
        assert not WorkItem.objects.filter(status="queued", kind="send_invitation").exists()

    def test_interrupted_write_requires_review_after_restart(self):
        invitation = Invitation.objects.create(
            person_id=self._person_id(),
            status=Invitation.Status.SENDING,
        )
        WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_INVITATION,
            status=WorkItem.Status.RUNNING,
            invitation=invitation,
            due_at=timezone.now(),
        )

        assert recover_interrupted_work() == 1
        invitation.refresh_from_db()
        assert invitation.status == "needs_review"

    def test_interrupted_message_keeps_the_invitation_accepted(self):
        invitation = Invitation.objects.create(
            person_id=self._person_id(),
            status=Invitation.Status.ACCEPTED,
        )
        message = Message.objects.create(
            invitation=invitation,
            body="Hello Ada",
            status=Message.Status.SENDING,
        )
        WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_MESSAGE,
            status=WorkItem.Status.RUNNING,
            invitation=invitation,
            message=message,
            due_at=timezone.now(),
        )

        assert recover_interrupted_work() == 1
        invitation.refresh_from_db()
        message.refresh_from_db()
        assert invitation.status == Invitation.Status.ACCEPTED
        assert message.status == Message.Status.NEEDS_REVIEW

    def test_acceptance_queues_and_sends_the_approved_auto_send_snapshot(self):
        client = AcceptedMessagingClient()
        person = Person.objects.create(name="CA Akhil Kumar", public_id="ada")
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.PENDING,
            sent_at=timezone.now(),
        )
        template = MessageTemplate.objects.create(
            body="Changed text",
            is_active=True,
            auto_send_enabled=True,
        )
        connection_import = ConnectionImport.objects.create(
            filename="people.csv",
            status=ConnectionImport.Status.COMPLETE,
            message_template=template,
            message_template_body="Hi, {first_name}. Thanks for connecting",
            message_delay_minutes=0,
            auto_message_enabled=True,
        )
        ConnectionRequest.objects.create(
            connection_import=connection_import,
            person=person,
            invitation=invitation,
            row_number=2,
            name=person.name,
            public_id=person.public_id,
            status=ConnectionRequest.Status.SENT,
            sent_at=invitation.sent_at,
        )
        WorkItem.objects.create(
            kind=WorkItem.Kind.CHECK_ACCEPTANCES,
            due_at=timezone.now(),
        )
        template.auto_send_enabled = False
        template.save(update_fields=["auto_send_enabled"])

        run_due_work(lambda: client)

        invitation.refresh_from_db()
        message = Message.objects.get(invitation=invitation)
        assert invitation.status == "accepted"
        assert message.body == "Hi, Akhil. Thanks for connecting"
        assert message.status == "sent"
        assert client.messages == [
            (
                "Hi, Akhil. Thanks for connecting",
                ["urn:li:fsd_profile:ada"],
            ),
        ]

    def test_invalid_template_snapshot_is_never_sent(self):
        client = AcceptedMessagingClient()
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.PENDING,
            sent_at=timezone.now(),
        )
        template = MessageTemplate.objects.create(
            body="Hello {dummy_name}",
            is_active=True,
            auto_send_enabled=True,
        )
        connection_import = ConnectionImport.objects.create(
            filename="people.csv",
            status=ConnectionImport.Status.COMPLETE,
            message_template=template,
            message_template_body="Hello {dummy_name}",
            message_delay_minutes=0,
            auto_message_enabled=True,
        )
        ConnectionRequest.objects.create(
            connection_import=connection_import,
            person=person,
            invitation=invitation,
            row_number=2,
            name=person.name,
            public_id=person.public_id,
            status=ConnectionRequest.Status.SENT,
            sent_at=invitation.sent_at,
        )
        WorkItem.objects.create(
            kind=WorkItem.Kind.CHECK_ACCEPTANCES,
            due_at=timezone.now(),
        )

        run_due_work(lambda: client)

        message = Message.objects.get(invitation=invitation)
        assert message.status == "failed"
        assert message.error == "Unknown message field: {dummy_name}."
        assert client.messages == []

    def test_message_waits_for_the_saved_delay_after_acceptance(self):
        client = AcceptedMessagingClient()
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.PENDING,
            sent_at=timezone.now(),
        )
        template = MessageTemplate.objects.create(
            body="Hello {first_name}",
            is_active=True,
            auto_send_enabled=True,
            delay_minutes=20,
        )
        connection_import = ConnectionImport.objects.create(
            filename="people.csv",
            status=ConnectionImport.Status.COMPLETE,
            message_template=template,
            message_template_body=template.body,
            message_delay_minutes=20,
            auto_message_enabled=True,
        )
        ConnectionRequest.objects.create(
            connection_import=connection_import,
            person=person,
            invitation=invitation,
            row_number=2,
            name=person.name,
            public_id=person.public_id,
            status=ConnectionRequest.Status.SENT,
            sent_at=invitation.sent_at,
        )
        WorkItem.objects.create(
            kind=WorkItem.Kind.CHECK_ACCEPTANCES,
            due_at=timezone.now(),
        )

        run_due_work(lambda: client)

        message = Message.objects.get(invitation=invitation)
        send_work = WorkItem.objects.get(
            kind=WorkItem.Kind.SEND_MESSAGE,
            message=message,
        )
        assert message.status == Message.Status.QUEUED
        assert send_work.due_at >= timezone.now() + timedelta(minutes=19)
        assert client.messages == []

    def test_queued_message_with_unresolved_field_is_never_sent(self):
        client = AcceptedMessagingClient()
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.ACCEPTED,
            sent_at=timezone.now(),
            accepted_at=timezone.now(),
        )
        message = Message.objects.create(
            invitation=invitation,
            body="Hello {dummy_name}",
            status=Message.Status.QUEUED,
            queued_at=timezone.now(),
        )
        work_item = WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_MESSAGE,
            invitation=invitation,
            message=message,
            due_at=timezone.now(),
        )

        run_due_work(lambda: client)

        message.refresh_from_db()
        work_item.refresh_from_db()
        assert message.status == Message.Status.FAILED
        assert message.error == (
            "Message contains an unresolved field and was not sent."
        )
        assert work_item.status == WorkItem.Status.FAILED
        assert client.messages == []

    def test_manually_queued_message_runs_through_the_worker(self):
        client = AcceptedMessagingClient()
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
        Invitation.objects.create(
            person=person,
            status=Invitation.Status.ACCEPTED,
            sent_at=timezone.now(),
            accepted_at=timezone.now(),
        )
        MessageTemplate.objects.create(
            body="Hello {first_name}",
            is_active=True,
            auto_send_enabled=False,
        )

        assert queue_messages_for_people([str(person.id)]) == 1

        run_due_work(lambda: client)

        message = Message.objects.get(invitation__person=person)
        assert message.status == Message.Status.SENT
        assert client.messages == [
            ("Hello Ada", ["urn:li:fsd_profile:ada"]),
        ]

    def test_failed_acceptance_check_waits_before_retrying(self):
        person = Person.objects.create(name="Ada", public_id="ada")
        Invitation.objects.create(
            person=person,
            status=Invitation.Status.PENDING,
            sent_at=timezone.now(),
        )
        completed_at = timezone.now()
        WorkItem.objects.create(
            kind=WorkItem.Kind.CHECK_ACCEPTANCES,
            status=WorkItem.Status.FAILED,
            due_at=completed_at,
            completed_at=completed_at,
        )

        next_check = enqueue_acceptance_check()

        assert next_check is not None
        assert next_check.due_at >= completed_at + ACCEPTANCE_INTERVAL

    def test_acceptance_check_uses_the_last_successful_check_as_its_cutoff(self):
        client = AcceptedMessagingClient()
        checked_at = timezone.now() - timedelta(hours=1)
        person = Person.objects.create(name="Ada", public_id="ada")
        Invitation.objects.create(
            person=person,
            status=Invitation.Status.PENDING,
            sent_at=timezone.now() - timedelta(days=10),
            checked_at=checked_at,
        )
        WorkItem.objects.create(
            kind=WorkItem.Kind.CHECK_ACCEPTANCES,
            due_at=timezone.now(),
        )

        run_due_work(lambda: client)

        assert client.since_ms == [int(checked_at.timestamp() * 1000)]

    @staticmethod
    def _person_id():
        return Person.objects.create(name="Ada", public_id="ada").id
