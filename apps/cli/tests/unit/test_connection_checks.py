import pytest

from linkedin_wrapper import LinkedinAPIError, LinkedinClient


class FakeLimiter:
    def acquire(self):
        pass


class GoneDriver:
    def execute_script(self, script, url):
        return {"status": 410, "body": {"status": 410}}


def test_reads_pending_sent_invitation_public_ids():
    client = object.__new__(LinkedinClient)
    client._api_get = lambda endpoint: {
        "data": {
            "elements": [
                {
                    "invitation": {
                        "invitee": {"trackingId": "opaque"},
                        "toMember": {
                            "publicIdentifier": "Ada-Lovelace",
                        },
                    }
                }
            ],
            "paging": {"total": 1},
        }
    }

    assert client.get_sent_invitation_public_ids() == {"ada-lovelace"}


def test_falls_back_to_the_legacy_sent_invitation_view():
    client = object.__new__(LinkedinClient)
    calls = []

    def api_get(endpoint):
        calls.append(endpoint)
        if "sentInvitationViewsV2" in endpoint:
            return {}
        return {
            "data": {
                "elements": [
                    {
                        "invitation": {
                            "toMember": {
                                "publicIdentifier": "grace-hopper",
                            }
                        }
                    }
                ],
                "paging": {"total": 1},
            }
        }

    client._api_get = api_get

    assert client.get_sent_invitation_public_ids() == {"grace-hopper"}
    assert len(calls) == 2


def test_search_relationship_marks_first_degree_as_connected():
    client = object.__new__(LinkedinClient)
    calls = []

    def search_people(keywords, limit, raise_for_status):
        calls.append((keywords, limit, raise_for_status))
        return [
            {"public_id": "not-ada", "connection_degree": "1st"},
            {"public_id": "ada", "connection_degree": "1st"},
        ]

    client.search_people = search_people

    assert client.get_connection_state("ada") == {
        "state": "connected",
        "public_id": "ada",
        "url": "",
    }
    assert calls == [("ada", 10, True)]


def test_search_relationship_marks_second_and_third_degree_as_not_connected():
    client = object.__new__(LinkedinClient)
    degrees = iter(["2nd", "3rd+"])
    client.search_people = lambda **kwargs: [
        {"public_id": kwargs["keywords"], "connection_degree": next(degrees)}
    ]

    assert client.get_connection_state("ada")["state"] == "not_connected"
    assert client.get_connection_state("grace")["state"] == "not_connected"


def test_search_relationship_falls_back_to_name_and_requires_exact_profile():
    client = object.__new__(LinkedinClient)
    calls = []

    def search_people(keywords, limit, raise_for_status):
        calls.append(keywords)
        if keywords == "ada":
            return [{"public_id": "ada-lovelace", "connection_degree": "1st"}]
        return [{"public_id": "ada", "connection_degree": "2nd"}]

    client.search_people = search_people

    assert client.get_connection_state("ada", name="Ada Lovelace")["state"] == (
        "not_connected"
    )
    assert calls == ["ada", "Ada Lovelace"]


def test_search_relationship_returns_a_renamed_profile():
    client = object.__new__(LinkedinClient)
    client.search_people = lambda **kwargs: [
        {
            "name": "CA Tejas Kandoi",
            "public_id": "ca-tejas-kandoi-linked-in",
            "url": "https://www.linkedin.com/in/ca-tejas-kandoi-linked-in/",
            "connection_degree": "2nd",
        }
    ]

    assert client.get_connection_state(
        "ca-tejas-kandoi-0b7b3476",
        name="CA Tejas Kandoi",
    ) == {
        "state": "not_connected",
        "public_id": "ca-tejas-kandoi-linked-in",
        "url": "https://www.linkedin.com/in/ca-tejas-kandoi-linked-in/",
    }


def test_search_relationship_returns_unknown_when_exact_profile_is_missing():
    client = object.__new__(LinkedinClient)
    client.search_people = lambda **kwargs: [
        {"public_id": "not-ada", "connection_degree": "1st"}
    ]

    assert client.get_connection_state("ada") == {
        "state": "unknown",
        "public_id": "",
        "url": "",
    }


def test_search_relationship_preserves_linkedin_http_errors():
    client = object.__new__(LinkedinClient)
    client.driver = GoneDriver()
    client._limiter = FakeLimiter()

    with pytest.raises(
        LinkedinAPIError,
        match=r"LinkedIn returned HTTP 410 Gone\.",
    ) as error:
        client.get_connection_state("ada")

    assert error.value.status == 410
