const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const test = require("node:test");

const { createUpdateManager } = require("../src/updates.cjs");

class FakeUpdater extends EventEmitter {
  async checkForUpdates() {
    this.emit("checking-for-update");
    this.emit("update-not-available", { version: "0.2.0" });
  }

  async downloadUpdate() {
    this.emit("download-progress", { percent: 42.4 });
    this.emit("update-downloaded", { version: "0.3.0" });
  }

  quitAndInstall(...arguments_) {
    this.installArguments = arguments_;
  }
}

test("checks for updates without downloading them", async () => {
  const updater = new FakeUpdater();
  const manager = createUpdateManager({
    updater,
    currentVersion: "0.2.0",
    enabled: true,
  });

  assert.equal(updater.autoDownload, false);
  assert.equal(updater.autoInstallOnAppQuit, false);
  assert.equal(updater.allowPrerelease, false);

  await manager.checkForUpdates();

  assert.deepEqual(manager.getState(), {
    status: "up-to-date",
    currentVersion: "0.2.0",
    availableVersion: null,
    progress: null,
    error: null,
  });
});

test("downloads and installs an available update", async () => {
  const updater = new FakeUpdater();
  const states = [];
  const manager = createUpdateManager({
    updater,
    currentVersion: "0.2.0",
    enabled: true,
    onStateChange: (state) => states.push(state),
  });

  updater.emit("update-available", { version: "0.3.0" });
  await manager.downloadUpdate();
  manager.installUpdate();

  assert.equal(states.some((state) => state.progress === 42.4), true);
  assert.equal(manager.getState().status, "downloaded");
  assert.deepEqual(updater.installArguments, []);
});

test("surfaces the exact update error", async () => {
  const updater = new FakeUpdater();
  updater.checkForUpdates = async () => {
    throw new Error("latest-mac.yml returned HTTP 404");
  };
  const manager = createUpdateManager({
    updater,
    currentVersion: "0.2.0",
    enabled: true,
  });

  await assert.rejects(manager.checkForUpdates(), /latest-mac.yml returned HTTP 404/);

  assert.equal(manager.getState().status, "error");
  assert.equal(manager.getState().error, "latest-mac.yml returned HTTP 404");
});

test("refuses update actions outside an installed app", async () => {
  const manager = createUpdateManager({
    updater: new FakeUpdater(),
    currentVersion: "0.2.0",
    enabled: false,
  });

  await assert.rejects(
    manager.checkForUpdates(),
    /Updates are available only in the installed app/,
  );
  assert.equal(manager.getState().status, "unavailable");
});
