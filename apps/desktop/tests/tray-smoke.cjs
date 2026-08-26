const { app, Menu, nativeImage, Tray } = require("electron");

const { createMenuTray } = require("../src/menu-tray.cjs");

let tray;

app.on("window-all-closed", () => {});
app.whenReady()
  .then(() => {
    if (process.platform === "darwin") app.setActivationPolicy("accessory");
    tray = createMenuTray({
      app,
      Menu,
      nativeImage,
      Tray,
      onOpen: () => {},
      onQuit: () => app.quit(),
    });

    setTimeout(() => {
      const bounds = tray.getBounds();
      console.log(`Menu tray bounds: ${JSON.stringify(bounds)}`);
      if (bounds.x < 0 || bounds.y < 0 || bounds.width <= 0 || bounds.height <= 0) {
        process.exitCode = 1;
        console.error("Menu tray was created outside the visible menu bar.");
      }
      tray.destroy();
      app.quit();
    }, 1000);
  })
  .catch((error) => {
    process.exitCode = 1;
    console.error(error);
    app.quit();
  });
