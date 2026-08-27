const UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000;

function createUpdateManager({ updater, currentVersion, enabled, onStateChange }) {
  if (!updater) throw new TypeError("An Electron updater is required.");
  if (!currentVersion) throw new TypeError("The current app version is required.");

  let state = {
    status: enabled ? "idle" : "unavailable",
    currentVersion,
    availableVersion: null,
    progress: null,
    error: null,
  };

  const listeners = [];

  function getState() {
    return { ...state };
  }

  function publish(changes) {
    state = { ...state, ...changes };
    onStateChange?.(getState());
  }

  function fail(error) {
    const message = error instanceof Error ? error.message : String(error);
    publish({ status: "error", progress: null, error: message });
  }

  function listen(event, listener) {
    updater.on(event, listener);
    listeners.push([event, listener]);
  }

  if (enabled) {
    updater.autoDownload = false;
    updater.autoInstallOnAppQuit = false;
    updater.allowPrerelease = false;

    listen("checking-for-update", () => {
      publish({ status: "checking", progress: null, error: null });
    });
    listen("update-available", (info) => {
      publish({
        status: "available",
        availableVersion: info.version,
        progress: null,
        error: null,
      });
    });
    listen("update-not-available", () => {
      publish({
        status: "up-to-date",
        availableVersion: null,
        progress: null,
        error: null,
      });
    });
    listen("download-progress", (progress) => {
      publish({ status: "downloading", progress: progress.percent, error: null });
    });
    listen("update-downloaded", (info) => {
      publish({
        status: "downloaded",
        availableVersion: info.version,
        progress: 100,
        error: null,
      });
    });
    listen("update-cancelled", () => {
      publish({ status: "available", progress: null, error: null });
    });
    listen("error", fail);
  }

  async function checkForUpdates({ downloadIfAvailable = false } = {}) {
    if (!enabled) throw new Error("Updates are available only in the installed app.");
    if (["checking", "downloading", "installing"].includes(state.status)) {
      throw new Error("An update action is already running.");
    }
    publish({ status: "checking", progress: null, error: null });
    try {
      await updater.checkForUpdates();
      if (downloadIfAvailable && state.status === "available") {
        return downloadUpdate();
      }
      return getState();
    } catch (error) {
      fail(error);
      throw error;
    }
  }

  async function downloadUpdate() {
    if (state.status !== "available") {
      throw new Error("No update is ready to download.");
    }
    publish({ status: "downloading", progress: 0, error: null });
    try {
      await updater.downloadUpdate();
      return getState();
    } catch (error) {
      fail(error);
      throw error;
    }
  }

  function installUpdate() {
    if (state.status !== "downloaded") {
      throw new Error("The update has not finished downloading.");
    }
    publish({ status: "installing", progress: 100, error: null });
    try {
      updater.quitAndInstall();
      return getState();
    } catch (error) {
      fail(error);
      throw error;
    }
  }

  function dispose() {
    for (const [event, listener] of listeners) {
      updater.removeListener(event, listener);
    }
  }

  return {
    checkForUpdates,
    dispose,
    downloadUpdate,
    getState,
    installUpdate,
  };
}

module.exports = { createUpdateManager, UPDATE_CHECK_INTERVAL_MS };
