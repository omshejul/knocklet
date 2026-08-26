from linkedin_wrapper import LinkedinClient


def test_get_recent_connections_resolves_normalized_profiles():
    client = object.__new__(LinkedinClient)
    client._api_get = lambda endpoint: {
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


def test_get_recent_connections_stops_at_the_cutoff():
    client = object.__new__(LinkedinClient)
    calls = []

    def api_get(endpoint):
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
