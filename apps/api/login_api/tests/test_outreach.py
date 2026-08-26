from django.test import TestCase
from django.utils import timezone

from login_api.models import Invitation, Message, Person
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
        Message.objects.create(
            invitation=invitation,
            body="Hello Ada",
            status=Message.Status.FAILED,
            error="LinkedIn returned status 429.",
        )

        result = list_people()

        assert result[0]["invitation_status"] == "accepted"
        assert result[0]["message_status"] == "failed"
        assert result[0]["message_error"] == "LinkedIn returned status 429."

    def test_lists_imported_person_without_an_invitation(self):
        Person.objects.create(name="Grace Hopper", public_id="grace")

        result = list_people()

        assert result[0]["invitation_status"] == "not_started"
        assert result[0]["message_status"] == "not_scheduled"
