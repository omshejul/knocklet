from django.test import TestCase
from django.utils import timezone

from login_api.models import Invitation, Message, Person, WorkItem
from login_api.outreach import list_people


class PeopleTests(TestCase):
    def test_lists_invitation_and_message_state_separately(self):
        person = Person.objects.create(
            name="Ada Lovelace",
            public_id="ada",
            linkedin_url="https://linkedin.com/in/ada",
        )
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
        due_at = timezone.now()
        WorkItem.objects.create(
            kind=WorkItem.Kind.SEND_MESSAGE,
            invitation=invitation,
            message=message,
            status=WorkItem.Status.FAILED,
            due_at=due_at,
        )

        result = list_people()

        assert result[0]["invitation_status"] == "accepted"
        assert result[0]["message_status"] == "failed"
        assert result[0]["message_error"] == "LinkedIn returned status 429."
        assert result[0]["message_body"] == "Hello Ada"
        assert result[0]["message_due_at"] == due_at.isoformat()

    def test_lists_imported_person_without_an_invitation(self):
        Person.objects.create(name="Grace Hopper", public_id="grace")

        result = list_people()

        assert result[0]["invitation_status"] == "not_started"
        assert result[0]["message_status"] == "not_scheduled"
        assert result[0]["message_body"] is None
        assert result[0]["message_due_at"] is None

    def test_message_details_do_not_add_a_query_per_person(self):
        for name in ["Ada", "Grace"]:
            person = Person.objects.create(name=name, public_id=name.lower())
            invitation = Invitation.objects.create(
                person=person,
                status=Invitation.Status.ACCEPTED,
            )
            message = Message.objects.create(
                invitation=invitation,
                body=f"Hello {name}",
            )
            WorkItem.objects.create(
                kind=WorkItem.Kind.SEND_MESSAGE,
                invitation=invitation,
                message=message,
                due_at=timezone.now(),
            )

        with self.assertNumQueries(1):
            assert len(list_people()) == 2
