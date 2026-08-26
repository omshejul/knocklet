const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

function writeUpdateMetadata({ zipPath, outputPath, version, releaseDate = new Date() }) {
  const zip = fs.readFileSync(zipPath);
  const filename = path.basename(zipPath);
  const sha512 = crypto.createHash("sha512").update(zip).digest("base64");
  const quote = (value) => JSON.stringify(value);
  const contents = [
    `version: ${quote(version)}`,
    "files:",
    `  - url: ${quote(filename)}`,
    `    sha512: ${quote(sha512)}`,
    `    size: ${zip.length}`,
    `path: ${quote(filename)}`,
    `sha512: ${quote(sha512)}`,
    `releaseDate: ${quote(releaseDate.toISOString())}`,
    "",
  ].join("\n");

  fs.writeFileSync(outputPath, contents);
  return { filename, sha512, size: zip.length };
}

if (require.main === module) {
  const [zipPath, outputPath, version] = process.argv.slice(2);
  if (!zipPath || !outputPath || !version) {
    throw new Error("Usage: write-update-metadata.cjs ZIP OUTPUT VERSION");
  }
  const metadata = writeUpdateMetadata({ zipPath, outputPath, version });
  console.log(`Wrote OTA metadata for ${metadata.filename} (${metadata.size} bytes).`);
}

module.exports = { writeUpdateMetadata };
