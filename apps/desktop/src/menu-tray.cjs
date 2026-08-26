const path = require("node:path");

const MENU_TRAY_GUID = "7f5a1d4d-5f09-4be1-9d0c-276f482743d5";

function createMenuTray({ app, Menu, nativeImage, Tray, onOpen, onQuit }) {
  const iconPath = app.isPackaged
    ? path.join(process.resourcesPath, "menuTemplate.png")
    : path.join(__dirname, "../assets/menuTemplate.png");
  const icon = nativeImage.createFromPath(iconPath);
  if (icon.isEmpty()) {
    throw new Error(`Menu icon could not be loaded from ${iconPath}`);
  }

  icon.setTemplateImage(true);
  const tray = new Tray(icon, MENU_TRAY_GUID);
  tray.setToolTip("Knocklet");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Open Knocklet", click: onOpen },
      { type: "separator" },
      { label: "Quit Knocklet", click: onQuit },
    ]),
  );
  return tray;
}

module.exports = { createMenuTray, MENU_TRAY_GUID };
