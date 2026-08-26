from django.db import IntegrityError
from django.test import TestCase

from login_api.models import (
    ConnectionImport,
    ConnectionRequest,
    Invitation,
    Message,
    MessageTemplate,
    Person,
    WorkItem,
)


class ConnectionRequestModelTests(TestCase):
    def test_persists_invitation_state(self):
        connection_import = ConnectionImport.objects.create(filename="people.csv")
        request = ConnectionRequest.objects.create(
            connection_import=connection_import,
            row_number=2,
            name="Ada Lovelace",
            linkedin_url="https://linkedin.com/in/ada-lovelace",
            public_id="ada-lovelace",
            status=ConnectionRequest.Status.SENT,
        )

        saved = ConnectionRequest.objects.get(pk=request.pk)

        assert saved.name == "Ada Lovelace"
        assert saved.status == "sent"
        assert saved.connection_import.filename == "people.csv"

    def test_rejects_two_records_for_the_same_csv_row(self):
        connection_import = ConnectionImport.objects.create(filename="people.csv")
        values = {
            "connection_import": connection_import,
            "row_number": 2,
            "name": "Ada Lovelace",
            "public_id": "ada-lovelace",
            "status": ConnectionRequest.Status.READY,
        }
        ConnectionRequest.objects.create(**values)

        with self.assertRaises(IntegrityError):
            ConnectionRequest.objects.create(**values)


class OutreachModelTests(TestCase):
    def test_normalizes_linkedin_public_id(self):
        person = Person.objects.create(
            name="Ada Lovelace",
            linkedin_url="https://linkedin.com/in/Ada-Lovelace",
            public_id=" Ada-Lovelace ",
        )

        assert person.normalized_public_id == "ada-lovelace"

    def test_keeps_invitation_and_message_states_separate(self):
        person = Person.objects.create(name="Ada", public_id="ada")
        invitation = Invitation.objects.create(
            person=person,
            status=Invitation.Status.ACCEPTED,
        )
        template = MessageTemplate.objects.create(
            body="Thanks for connecting, {first_name}.",
        )
        message = Message.objects.create(
            invitation=invitation,
            template=template,
            body="Thanks for connecting, Ada.",
        )
        work_item = WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_MESSAGE,
            message=message,
            invitation=invitation,
            due_at=invitation.created_at,
        )

        assert invitation.status == "accepted"
        assert message.status == "queued"
        assert work_item.status == "queued"
