import io

from django.test import SimpleTestCase, TransactionTestCase
from openpyxl import Workbook

from login_api.connection_imports import ConnectionImportStore, parse_connection_file
from login_api.models import ConnectionRequest


def _xlsx(rows: list[list[str]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


class FakeLinkedInClient:
    def __init__(self, pending=None, connection_states=None):
        self.public_ids = []
        self.checked_profiles = []
        self.pending = pending or set()
        self.connection_states = connection_states or {}

    def get_sent_invitation_public_ids(self):
        return self.pending

    def get_connection_state(self, public_id, name=""):
        self.checked_profiles.append((public_id, name))
        return self.connection_states.get(public_id, "not_connected")

    def add_connection(self, profile_public_id: str):
        self.public_ids.append(profile_public_id)
        return {"status": 201}


class FakeAcceptanceClient:
    def get_recent_connections(self, max_results, since_ms):
        return [
            {
                "public_id": "ada",
                "connected_at": since_ms + 1_000,
            }
        ]


class FailingPreflightClient(FakeLinkedInClient):
    def get_connection_state(self, public_id, name=""):
        error = RuntimeError("LinkedIn returned HTTP 410 Gone.")
        error.status = 410
        raise error


class ConnectionImportParsingTests(SimpleTestCase):
    def test_parses_common_clay_people_columns(self):
        connection_import = parse_connection_file(
            b"Name,First Name,Last Name,LinkedIn URL\nAda Lovelace,Ada,Lovelace,https://www.linkedin.com/in/ada-lovelace/\n",
            "people.csv",
        )

        assert connection_import.people[0].name == "Ada Lovelace"
        assert connection_import.people[0].public_id == "ada-lovelace"
        assert connection_import.people[0].status == "ready"

    def test_keeps_invalid_and_duplicate_rows_in_preview(self):
        connection_import = parse_connection_file(
            b"Full Name,LinkedIn Profile URL\nAda,linkedin.com/in/ada\nAda Again,https://linkedin.com/in/ada\nMissing,\n",
            "people.csv",
        )

        assert [person.status for person in connection_import.people] == [
            "ready",
            "duplicate",
            "invalid",
        ]

    def test_detects_linkedin_urls_in_an_arbitrarily_named_csv_column(self):
        connection_import = parse_connection_file(
            b"Full Name,Profile\nAda Lovelace,https://linkedin.com/in/ada-lovelace\n",
            "people.csv",
        )

        assert connection_import.people[0].public_id == "ada-lovelace"

    def test_parses_xlsx_and_detects_the_linkedin_url_column(self):
        connection_import = parse_connection_file(
            _xlsx(
                [
                    ["Full Name", "Website", "Profile"],
                    ["Ada Lovelace", "https://example.com", "linkedin.com/in/ada"],
                ]
            ),
            "people.xlsx",
        )

        assert connection_import.people[0].name == "Ada Lovelace"
        assert connection_import.people[0].public_id == "ada"


class ConnectionImportPersistenceTests(TransactionTestCase):
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
        assert completed["progress_percent"] == 100

    def test_import_survives_store_restart(self):
        connection_import = ConnectionImportStore().create(
            b"Name,LinkedIn URL\nAda,https://linkedin.com/in/ada\n",
            "people.csv",
        )

        loaded = ConnectionImportStore().get(connection_import["id"])

        assert loaded["filename"] == "people.csv"
        assert loaded["people"][0]["public_id"] == "ada"

    def test_marks_a_previously_sent_profile_as_duplicate(self):
        client = FakeLinkedInClient()
        store = ConnectionImportStore(client_factory=lambda: client)
        first_import = store.create(
            b"Name,LinkedIn URL\nAda,https://linkedin.com/in/ada\n",
            "first.csv",
        )
        store.approve(first_import["id"])
        store.wait(first_import["id"])

        second_import = store.create(
            b"Name,LinkedIn URL\nAda,https://linkedin.com/in/ada\n",
            "second.csv",
        )

        assert second_import["people"][0]["status"] == "duplicate"
        assert second_import["skipped_count"] == 1

    def test_refresh_acceptance_persists_new_connections(self):
        sender = FakeLinkedInClient()
        store = ConnectionImportStore(client_factory=lambda: sender)
        connection_import = store.create(
            b"Name,LinkedIn URL\nAda,https://linkedin.com/in/ada\nGrace,https://linkedin.com/in/grace\n",
            "people.csv",
        )
        store.approve(connection_import["id"])
        store.wait(connection_import["id"])

        result = ConnectionImportStore(
            client_factory=lambda: FakeAcceptanceClient()
        ).refresh_acceptance()

        assert result["checked_count"] == 2
        assert result["accepted_count"] == 1
        assert ConnectionRequest.objects.get(public_id="ada").status == "accepted"
        assert ConnectionRequest.objects.get(public_id="grace").checked_at is not None

    def test_preflight_skips_pending_and_connected_profiles(self):
        client = FakeLinkedInClient(
            pending={"ada"},
            connection_states={"grace": "connected", "linus": "not_connected"},
        )
        store = ConnectionImportStore(client_factory=lambda: client)
        connection_import = store.create(
            b"Name,LinkedIn URL\nAda,https://linkedin.com/in/ada\nGrace,https://linkedin.com/in/grace\nLinus,https://linkedin.com/in/linus\n",
            "people.csv",
        )

        store.approve(connection_import["id"])
        completed = store.wait(connection_import["id"])

        assert client.public_ids == ["linus"]
        assert client.checked_profiles == [
            ("grace", "Grace"),
            ("linus", "Linus"),
        ]
        assert [person["status"] for person in completed["people"]] == [
            "pending",
            "connected",
            "sent",
        ]
        assert completed["pending_count"] == 1
        assert completed["connected_count"] == 1
        assert completed["skipped_count"] == 2

    def test_preflight_does_not_send_when_status_is_unknown(self):
        client = FakeLinkedInClient(connection_states={"ada": "unknown"})
        store = ConnectionImportStore(client_factory=lambda: client)
        connection_import = store.create(
            b"Name,LinkedIn URL\nAda,https://linkedin.com/in/ada\n",
            "people.csv",
        )

        store.approve(connection_import["id"])
        completed = store.wait(connection_import["id"])

        assert client.public_ids == []
        assert completed["people"][0]["status"] == "failed"
        assert completed["people"][0]["error"] == (
            "Connection status could not be confirmed."
        )

    def test_preflight_preserves_the_linkedin_http_error(self):
        client = FailingPreflightClient()
        store = ConnectionImportStore(client_factory=lambda: client)
        connection_import = store.create(
            b"Name,LinkedIn URL\nAda,https://linkedin.com/in/ada\n",
            "people.csv",
        )

        store.approve(connection_import["id"])
        completed = store.wait(connection_import["id"])

        assert client.public_ids == []
        assert completed["people"][0]["status"] == "failed"
        assert completed["people"][0]["provider_status"] == 410
        assert completed["people"][0]["error"] == (
            "LinkedIn returned HTTP 410 Gone."
        )
