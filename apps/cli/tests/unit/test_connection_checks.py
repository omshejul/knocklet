from linkedin_wrapper import LinkedinClient


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


def test_reads_direct_connection_distance():
    client = object.__new__(LinkedinClient)
    client.get_profile_network_info = lambda public_id: {
        "data": {"distance": {"value": "DISTANCE_1"}}
    }

    assert client.get_connection_state("ada") == "connected"


def test_returns_unknown_when_connection_distance_is_missing():
    client = object.__new__(LinkedinClient)
    client.get_profile_network_info = lambda public_id: {"data": {}}

    assert client.get_connection_state("ada") == "unknown"
