from django.db import IntegrityError
from django.test import TestCase

from login_api.models import ConnectionImport, ConnectionRequest


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
