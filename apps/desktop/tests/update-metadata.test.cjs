const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  writeUpdateMetadata,
} = require("../scripts/write-update-metadata.cjs");

test("writes ZIP-only metadata from the final OTA artifact", (context) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "knocklet-update-metadata-"));
  context.after(() => fs.rmSync(directory, { recursive: true }));
  const zipPath = path.join(directory, "Knocklet-0.2.0-arm64.zip");
  const outputPath = path.join(directory, "latest-mac.yml");
  fs.writeFileSync(zipPath, "final zip bytes");

  const result = writeUpdateMetadata({
    zipPath,
    outputPath,
    version: "0.2.0",
    releaseDate: new Date("2026-08-27T00:00:00.000Z"),
  });
  const metadata = fs.readFileSync(outputPath, "utf8");

  assert.equal(result.size, 15);
  assert.equal(metadata.startsWith('version: "0.2.0"'), true);
  assert.equal(metadata.includes('url: "Knocklet-0.2.0-arm64.zip"'), true);
  assert.equal(metadata.includes("size: 15"), true);
  assert.equal(
    metadata.includes('releaseDate: "2026-08-27T00:00:00.000Z"'),
    true,
  );
  assert.equal(metadata.includes(".dmg"), false);
});
