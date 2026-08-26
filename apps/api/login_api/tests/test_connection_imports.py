from django.test import SimpleTestCase

from login_api.connection_imports import ConnectionImportStore, parse_clay_csv


class FakeLinkedInClient:
    def __init__(self):
        self.public_ids = []

    def add_connection(self, profile_public_id: str):
        self.public_ids.append(profile_public_id)
        return {"status": 201}


class ConnectionImportTests(SimpleTestCase):
    def test_parses_common_clay_people_columns(self):
        connection_import = parse_clay_csv(
            b"Name,First Name,Last Name,LinkedIn URL\nAda Lovelace,Ada,Lovelace,https://www.linkedin.com/in/ada-lovelace/\n",
            "people.csv",
        )

        assert connection_import.people[0].name == "Ada Lovelace"
        assert connection_import.people[0].public_id == "ada-lovelace"
        assert connection_import.people[0].status == "ready"

    def test_keeps_invalid_and_duplicate_rows_in_preview(self):
        connection_import = parse_clay_csv(
            b"Full Name,LinkedIn Profile URL\nAda,linkedin.com/in/ada\nAda Again,https://linkedin.com/in/ada\nMissing,\n",
            "people.csv",
        )

        assert [person.status for person in connection_import.people] == [
            "ready",
            "duplicate",
            "invalid",
        ]

    def test_approval_sends_only_ready_people(self):
        client = FakeLinkedInClient()
        store = ConnectionImportStore(client_factory=lambda: client)
        connection_import = store.create(
            b"Name,LinkedIn URL\nAda,https://linkedin.com/in/ada\nBad,https://linkedin.com/company/example\n",
            "people.csv",
        )

        store.approve(connection_import["id"])
        completed = store.wait(connection_import["id"])

        assert client.public_ids == ["ada"]
        assert completed["status"] == "complete"
        assert completed["sent_count"] == 1
        assert completed["skipped_count"] == 1
