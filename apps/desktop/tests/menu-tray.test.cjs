const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const {
  createMenuTray,
  MENU_TRAY_GUID,
} = require("../src/menu-tray.cjs");

test("creates a persistent template tray with open and quit actions", () => {
  const originalResourcesPath = process.resourcesPath;
  process.resourcesPath = "/Applications/Knocklet.app/Contents/Resources";
  const calls = [];
  const image = {
    isEmpty: () => false,
    setTemplateImage: (value) => calls.push(["template", value]),
  };
  const menu = {};
  let template;

  class FakeTray {
    constructor(trayImage, guid) {
      calls.push(["tray", trayImage, guid]);
    }

    setToolTip(value) {
      calls.push(["tooltip", value]);
    }

    setContextMenu(value) {
      calls.push(["menu", value]);
    }
  }

  const onOpen = () => {};
  const onQuit = () => {};
  try {
    const tray = createMenuTray({
      app: { isPackaged: true },
      Menu: {
        buildFromTemplate: (value) => {
          template = value;
          return menu;
        },
      },
      nativeImage: {
        createFromPath: (value) => {
          calls.push(["path", value]);
          return image;
        },
      },
      Tray: FakeTray,
      onOpen,
      onQuit,
    });

    assert.ok(tray instanceof FakeTray);
    assert.deepEqual(calls[0], [
      "path",
      path.join(process.resourcesPath, "menuTemplate.png"),
    ]);
    assert.deepEqual(calls[1], ["template", true]);
    assert.deepEqual(calls[2], ["tray", image, MENU_TRAY_GUID]);
    assert.deepEqual(calls[3], ["tooltip", "Knocklet"]);
    assert.deepEqual(calls[4], ["menu", menu]);
    assert.equal(template[0].click, onOpen);
    assert.equal(template[2].click, onQuit);
  } finally {
    if (originalResourcesPath === undefined) delete process.resourcesPath;
    else process.resourcesPath = originalResourcesPath;
  }
});

test("fails clearly when the menu icon cannot be loaded", () => {
  assert.throws(
    () =>
      createMenuTray({
        app: { isPackaged: false },
        Menu: {},
        nativeImage: {
          createFromPath: () => ({ isEmpty: () => true }),
        },
        Tray: class {},
        onOpen: () => {},
        onQuit: () => {},
      }),
    /Menu icon could not be loaded/,
  );
});

test("packages an agent app with correctly sized template images", () => {
  const packageJson = require("../package.json");
  const assetDirectory = path.join(__dirname, "../assets");

  assert.equal(packageJson.build.mac.extendInfo.LSUIElement, true);
  assert.deepEqual(pngSize(path.join(assetDirectory, "menuTemplate.png")), [22, 22]);
  assert.deepEqual(pngSize(path.join(assetDirectory, "menuTemplate@2x.png")), [44, 44]);
});

function pngSize(filePath) {
  const contents = fs.readFileSync(filePath);
  assert.equal(contents.subarray(1, 4).toString("ascii"), "PNG");
  return [contents.readUInt32BE(16), contents.readUInt32BE(20)];
}
