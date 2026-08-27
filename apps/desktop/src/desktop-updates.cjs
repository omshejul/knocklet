const { dialog, ipcMain, Menu } = require("electron");
const { autoUpdater } = require("electron-updater");

const {
  createUpdateManager,
  UPDATE_CHECK_INTERVAL_MS,
} = require("./updates.cjs");

function createDesktopUpdates({ app, getTray, getWindow, openWindow, setQuitting }) {
  let checkTimer;
  const manager = createUpdateManager({
    updater: autoUpdater,
    currentVersion: app.getVersion(),
    enabled: app.isPackaged,
    onStateChange: broadcast,
  });

  function run(action) {
    Promise.resolve()
      .then(action)
      .catch((error) => dialog.showErrorBox("Knocklet update failed", error.message));
  }

  function install() {
    setQuitting(true);
    try {
      return manager.installUpdate();
    } catch (error) {
      setQuitting(false);
      throw error;
    }
  }

  function updateMenuItem(state) {
    if (state.status === "checking") {
      return { label: "Checking for Updates...", enabled: false };
    }
    if (state.status === "available") {
      return {
        label: `Download ${state.availableVersion}`,
        click: () => run(manager.downloadUpdate),
      };
    }
    if (state.status === "downloading") {
      return {
        label: `Downloading ${Math.round(state.progress ?? 0)}%`,
        enabled: false,
      };
    }
    if (state.status === "downloaded") {
      return { label: "Restart to Update", click: () => run(install) };
    }
    if (state.status === "installing") {
      return { label: "Installing Update...", enabled: false };
    }
    if (state.status === "unavailable") {
      return { label: "Updates require the installed app", enabled: false };
    }
    return {
      label: "Check for Updates",
      click: () =>
        run(() => manager.checkForUpdates({ downloadIfAvailable: true })),
    };
  }

  function refreshMenu() {
    const tray = getTray();
    if (!tray) return;
    const state = manager.getState();
    const updateError = state.error
      ? [{ label: "Update failed", sublabel: state.error, enabled: false }]
      : [];
    tray.setToolTip(`Knocklet ${state.currentVersion}`);
    tray.setContextMenu(
      Menu.buildFromTemplate([
        { label: "Open Knocklet", click: openWindow },
        { type: "separator" },
        { label: `Knocklet ${state.currentVersion}`, enabled: false },
        updateMenuItem(state),
        ...updateError,
        { type: "separator" },
        {
          label: "Quit Knocklet",
          click: () => {
            setQuitting(true);
            app.quit();
          },
        },
      ]),
    );
  }

  function broadcast(state) {
    refreshMenu();
    const window = getWindow();
    if (window && !window.isDestroyed()) {
      window.webContents.send("updates:state", state);
    }
  }

  function checkAutomatically() {
    const status = manager.getState().status;
    if (["available", "downloading", "downloaded", "installing"].includes(status)) return;
    manager.checkForUpdates().catch((error) => {
      console.error(`Automatic update check failed: ${error.message}`);
    });
  }

  function start() {
    refreshMenu();
    if (!app.isPackaged) return;
    checkAutomatically();
    checkTimer = setInterval(checkAutomatically, UPDATE_CHECK_INTERVAL_MS);
  }

  function dispose() {
    clearInterval(checkTimer);
    manager.dispose();
    for (const channel of [
      "updates:get-state",
      "updates:check",
      "updates:download",
      "updates:install",
    ]) {
      ipcMain.removeHandler(channel);
    }
  }

  ipcMain.handle("updates:get-state", () => manager.getState());
  ipcMain.handle("updates:check", () =>
    manager.checkForUpdates({ downloadIfAvailable: true }),
  );
  ipcMain.handle("updates:download", () => manager.downloadUpdate());
  ipcMain.handle("updates:install", () => {
    return install();
  });

  return { dispose, start };
}

module.exports = { createDesktopUpdates };
