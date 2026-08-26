from django.test import TransactionTestCase
from django.utils import timezone

from login_api.automation import (
    ACCEPTANCE_INTERVAL,
    enqueue_acceptance_check,
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

    def get_sent_invitation_public_ids(self):
        return set()

    def get_connection_state(self, public_id, name=""):
        return "not_connected"

    def add_connection(self, profile_public_id):
        self.sent.append(profile_public_id)
        return {"status": 201}


class UncertainClient(SafeClient):
    def add_connection(self, profile_public_id):
        raise TimeoutError("LinkedIn did not confirm the invitation.")


class AcceptedMessagingClient:
    def __init__(self):
        self.messages = []

    def get_recent_connections(self, max_results, since_ms):
        return [{"public_id": "ada", "connected_at": since_ms + 1000}]

    def get_profile(self, public_id):
        return {"entityUrn": "urn:li:fsd_profile:ada"}

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

    def test_acceptance_queues_and_sends_the_approved_template_snapshot(self):
        client = AcceptedMessagingClient()
        person = Person.objects.create(name="Ada Lovelace", public_id="ada")
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
            message_template_body="Hello {first_name}",
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

        invitation.refresh_from_db()
        message = Message.objects.get(invitation=invitation)
        assert invitation.status == "accepted"
        assert message.body == "Hello Ada"
        assert message.status == "sent"
        assert client.messages == [
            ("Hello Ada", ["urn:li:fsd_profile:ada"]),
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

    @staticmethod
    def _person_id():
        return Person.objects.create(name="Ada", public_id="ada").id
