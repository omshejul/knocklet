const assert = require("node:assert/strict");
const test = require("node:test");

const { createExternalLinkHandler } = require("../src/external-links.cjs");

test("opens HTTPS links in the default browser and denies an app popup", () => {
  const openedUrls = [];
  const handler = createExternalLinkHandler({
    shell: {
      openExternal: async (url) => openedUrls.push(url),
    },
    onError: assert.fail,
  });

  const result = handler({ url: "https://www.linkedin.com/in/example" });

  assert.deepEqual(result, { action: "deny" });
  assert.deepEqual(openedUrls, ["https://www.linkedin.com/in/example"]);
});

test("blocks links that could launch a local command", () => {
  const errors = [];
  const handler = createExternalLinkHandler({
    shell: {
      openExternal: async () => assert.fail("unsafe link was opened"),
    },
    onError: (error) => errors.push(error.message),
  });

  const result = handler({ url: "file:///Applications/Calculator.app" });

  assert.deepEqual(result, { action: "deny" });
  assert.deepEqual(errors, ["Unsupported link protocol: file:"]);
});

test("reports a default-browser failure", async () => {
  const errors = [];
  const handler = createExternalLinkHandler({
    shell: {
      openExternal: async () => {
        throw new Error("No browser is available");
      },
    },
    onError: (error) => errors.push(error.message),
  });

  handler({ url: "https://www.linkedin.com/in/example" });
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepEqual(errors, ["No browser is available"]);
});
