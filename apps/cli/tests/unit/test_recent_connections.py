from linkedin_wrapper import LinkedinAPIError, LinkedinClient


def test_get_recent_connections_resolves_normalized_profiles():
    client = object.__new__(LinkedinClient)
    client._api_get = lambda endpoint, **kwargs: {
        "data": {"*elements": ["urn:li:fsd_connection:(me,ada)"]},
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.relationships.Connection",
                "entityUrn": "urn:li:fsd_connection:(me,ada)",
                "createdAt": 1_725_000_000_000,
                "*connectedMemberResolutionResult": "urn:li:fsd_profile:ada",
            },
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
                "entityUrn": "urn:li:fsd_profile:ada",
                "publicIdentifier": "ada-lovelace",
            },
        ],
    }

    assert client.get_recent_connections() == [
        {
            "public_id": "ada-lovelace",
            "connected_at": 1_725_000_000_000,
        }
    ]


def test_get_recent_connections_resolves_embedded_profiles():
    client = object.__new__(LinkedinClient)
    client._api_get = lambda endpoint, **kwargs: {
        "data": {
            "elements": [
                {
                    "entityUrn": "urn:li:fsd_connection:(me,akhil)",
                    "createdAt": 1_725_000_000_000,
                    "connectedMemberResolutionResult": {
                        "entityUrn": "urn:li:fsd_profile:akhil",
                        "publicIdentifier": "akhilkumar-ca",
                    },
                }
            ]
        }
    }

    assert client.get_recent_connections() == [
        {
            "public_id": "akhilkumar-ca",
            "connected_at": 1_725_000_000_000,
        }
    ]


def test_get_recent_connections_stops_at_the_cutoff():
    client = object.__new__(LinkedinClient)
    calls = []

    def api_get(endpoint, **kwargs):
        calls.append(endpoint)
        references = [f"urn:li:fsd_connection:(me,{index})" for index in range(40)]
        included = []
        for index, reference in enumerate(references):
            included.extend(
                [
                    {
                        "entityUrn": reference,
                        "createdAt": 2_000 - index,
                        "*connectedMemberResolutionResult": f"urn:li:fsd_profile:{index}",
                    },
                    {
                        "entityUrn": f"urn:li:fsd_profile:{index}",
                        "publicIdentifier": f"person-{index}",
                    },
                ]
            )
        return {"data": {"*elements": references}, "included": included}

    client._api_get = api_get

    client.get_recent_connections(since_ms=1_980)

    assert len(calls) == 1


def test_get_recent_connections_falls_back_when_the_dash_endpoint_is_gone():
    client = object.__new__(LinkedinClient)
    calls = []

    def api_get(endpoint, **kwargs):
        calls.append(endpoint)
        if "/relationships/dash/connections" in endpoint:
            raise LinkedinAPIError(410)
        return {
            "elements": [
                {
                    "createdAt": 1_725_000_000_000,
                    "miniProfile": {"publicIdentifier": "ada-lovelace"},
                }
            ]
        }

    client._api_get = api_get

    assert client.get_recent_connections(max_results=1) == [
        {
            "public_id": "ada-lovelace",
            "connected_at": 1_725_000_000_000,
        }
    ]
    assert "/relationships/dash/connections" in calls[0]
    assert calls[1].endswith("&sortType=RECENTLY_ADDED")
