from linkedin_wrapper import LinkedinClient


class FakeLimiter:
    def __init__(self):
        self.calls = 0

    def acquire(self):
        self.calls += 1


class ComposeDriver:
    def __init__(self):
        self.urls = []
        self.message = None

    def get(self, url):
        self.urls.append(url)

    def execute_script(self, script, *args):
        if "await fetch" in script:
            return {"status": 400}
        if "performance.now()" in script:
            return 100
        if "document.execCommand" in script:
            self.message = args[0]
            return True
        if "responseStatus" in script:
            return 200
        return True


def test_send_message_uses_linkedin_compose_and_confirms_delivery():
    driver = ComposeDriver()
    client = object.__new__(LinkedinClient)
    client.driver = driver
    client._navigate = driver.get
    client._limiter = FakeLimiter()

    result = client.send_message(
        message_body="Test message",
        recipients=["urn:li:fsd_profile:recipient-id"],
    )

    assert result == {"status": 200}
    assert driver.urls[0].startswith("https://www.linkedin.com/messaging/compose/?")
    assert "recipient=recipient-id" in driver.urls[0]
    assert driver.message == "Test message"
    assert client._limiter.calls == 1


def test_send_message_to_conversation_uses_the_counted_post_helper():
    client = object.__new__(LinkedinClient)
    calls = []
    client._api_post = lambda endpoint, payload: calls.append(
        (endpoint, payload)
    ) or {"status": 201}

    result = client.send_message(
        message_body="Test message",
        conversation_urn_id="conversation-id",
    )

    assert result == {"status": 201}
    assert calls[0][0] == "/messaging/conversations/conversation-id/events"
