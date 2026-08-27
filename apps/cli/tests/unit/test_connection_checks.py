import time

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
    client._api_get = lambda endpoint, **kwargs: {
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


def test_does_not_retry_a_failed_sent_invitation_read_with_a_broken_endpoint():
    client = object.__new__(LinkedinClient)
    calls = []

    def api_get(endpoint, **kwargs):
        calls.append(endpoint)
        raise LinkedinAPIError(400)

    client._api_get = api_get

    with pytest.raises(LinkedinAPIError, match="HTTP 400 Bad Request"):
        client.get_sent_invitation_public_ids()

    assert len(calls) == 1
    assert "sentInvitationViewsV2" in calls[0]


def test_empty_current_sent_invitation_view_does_not_call_legacy_endpoint():
    client = object.__new__(LinkedinClient)
    calls = []

    def api_get(endpoint, **kwargs):
        calls.append(endpoint)
        return {"data": {"elements": [], "paging": {"total": 0}}}

    client._api_get = api_get

    assert client.get_sent_invitation_public_ids() == set()
    assert len(calls) == 1


def test_reuses_a_recent_sent_invitation_snapshot():
    client = object.__new__(LinkedinClient)
    calls = []

    def api_get(endpoint, **kwargs):
        calls.append(endpoint)
        return {"data": {"elements": [], "paging": {"total": 0}}}

    client._api_get = api_get

    assert client.get_sent_invitation_public_ids() == set()
    assert client.get_sent_invitation_public_ids() == set()
    assert len(calls) == 1


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
        "urn_id": "",
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
        "urn_id": "",
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
        "urn_id": "",
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


def test_connection_state_returns_the_search_profile_urn():
    client = object.__new__(LinkedinClient)
    client.search_people = lambda **kwargs: [
        {
            "public_id": "ada",
            "connection_degree": "2nd",
            "urn_id": "urn:li:fsd_profile:ada-id",
        }
    ]

    assert client.get_connection_state("ada")["urn_id"] == (
        "urn:li:fsd_profile:ada-id"
    )


def test_search_results_extract_the_profile_urn_from_the_result_wrapper():
    client = object.__new__(LinkedinClient)
    data = {
        "elements": [
            {
                "items": [
                    {
                        "itemUnion": {
                            "entityResult": {
                                "title": {"text": "Ada Lovelace"},
                                "navigationUrl": "https://www.linkedin.com/in/ada/",
                                "entityUrn": (
                                    "urn:li:fsd_entityResultViewModel:"
                                    "(urn:li:fsd_profile:ada-id,SEARCH_SRP)"
                                ),
                            }
                        }
                    }
                ]
            }
        ]
    }

    assert client._extract_search_results(data)[0]["urn_id"] == (
        "urn:li:fsd_profile:ada-id"
    )


def test_get_profile_urn_uses_only_the_base_profile_request():
    client = object.__new__(LinkedinClient)
    calls = []

    def api_get(endpoint):
        calls.append(endpoint)
        return {"elements": [{"entityUrn": "urn:li:fsd_profile:ada-id"}]}

    client._api_get = api_get

    assert client.get_profile_urn("ada") == "urn:li:fsd_profile:ada-id"
    assert len(calls) == 1


def test_add_connection_reuses_the_profile_urn_from_search():
    client = object.__new__(LinkedinClient)
    calls = []
    client._sent_invitation_cache = (time.monotonic(), set())
    client.get_profile_urn = lambda public_id: pytest.fail(
        f"unexpected profile lookup for {public_id}"
    )
    client._api_post = lambda endpoint, payload: calls.append(
        (endpoint, payload)
    ) or {"status": 201}

    result = client.add_connection(
        profile_public_id="ada",
        profile_urn="urn:li:fsd_profile:ada-id",
    )

    assert result == {"status": 201}
    assert calls == [
        (
            "/voyagerRelationshipsDashMemberRelationships"
            "?action=verifyQuotaAndCreateV2",
            {
                "invitee": {
                    "inviteeUnion": {
                        "memberProfile": "urn:li:fsd_profile:ada-id",
                    }
                }
            },
        )
    ]
    assert client.get_sent_invitation_public_ids() == {"ada"}


def test_add_connection_includes_an_optional_note():
    client = object.__new__(LinkedinClient)
    calls = []
    client._sent_invitation_cache = None
    client._api_post = lambda endpoint, payload: calls.append(
        (endpoint, payload)
    ) or {"status": 201}

    client.add_connection(
        profile_public_id="ada",
        profile_urn="urn:li:fsd_profile:ada-id",
        message="This is a test, please ignore.",
    )

    assert calls[0][1]["customMessage"] == "This is a test, please ignore."
