from linkedin_wrapper import LinkedinClient


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

    result = client.send_message(
        message_body="Test message",
        recipients=["urn:li:fsd_profile:recipient-id"],
    )

    assert result == {"status": 200}
    assert driver.urls[0].startswith("https://www.linkedin.com/messaging/compose/?")
    assert "recipient=recipient-id" in driver.urls[0]
    assert driver.message == "Test message"
