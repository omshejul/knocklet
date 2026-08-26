from django.test import TransactionTestCase
from django.utils import timezone

from login_api.automation import recover_interrupted_work, run_due_work
from login_api.connection_imports import ConnectionImportStore
from login_api.models import Invitation, WorkItem


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

    @staticmethod
    def _person_id():
        from login_api.models import Person

        return Person.objects.create(name="Ada", public_id="ada").id
