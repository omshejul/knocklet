const { app, BrowserWindow, dialog, Menu, nativeImage, Tray } = require("electron");
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const API_ADDRESS = "127.0.0.1:47138";
const API_URL = `http://${API_ADDRESS}/api/health`;
const WEB_PORT = 47139;
const WEB_URL = `http://127.0.0.1:${WEB_PORT}`;

let apiProcess;
let mainWindow;
let quitting = false;
let tray;
let webServer;
let workerProcess;

function packagedPath(name) {
  if (app.isPackaged) return path.join(process.resourcesPath, name);
  if (name === "web") return path.join(__dirname, "../../web/out");
  return path.join(__dirname, "../runtime-dist/knocklet-runtime");
}

function runtimeEnvironment() {
  return {
    ...process.env,
    DJANGO_DEBUG: "false",
    KNOCKLET_API_ADDRESS: API_ADDRESS,
    LINKEDIN_DATA_DIR: app.getPath("userData"),
    WEB_ORIGIN: WEB_URL,
  };
}

function runMigrations(runtime, environment, logDescriptor, logPath) {
  const result = spawnSync(runtime, ["migrate"], {
    env: environment,
    stdio: ["ignore", logDescriptor, logDescriptor],
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`Database migration failed. See ${logPath}`);
  }
}

function startRuntime(runtime, mode, environment, logDescriptor) {
  const child = spawn(runtime, [mode], {
    detached: true,
    env: environment,
    stdio: ["ignore", logDescriptor, logDescriptor],
  });
  child.on("error", (error) => stopAfterRuntimeFailure(mode, error));
  child.on("exit", (code, signal) => {
    if (!quitting) {
      stopAfterRuntimeFailure(
        mode,
        new Error(`${mode} stopped with ${signal ?? `exit code ${code}`}.`),
      );
    }
  });
  return child;
}

function stopAfterRuntimeFailure(mode, error) {
  if (quitting) return;
  quitting = true;
  dialog.showErrorBox("Knocklet stopped", `${mode}: ${error.message}`);
  app.quit();
}

function stopRuntime(child) {
  if (!child?.pid || child.killed) return;
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch (error) {
    if (error.code !== "ESRCH") console.error(error);
  }
}

function startStaticServer(root) {
  const contentTypes = new Map([
    [".css", "text/css; charset=utf-8"],
    [".html", "text/html; charset=utf-8"],
    [".ico", "image/x-icon"],
    [".js", "text/javascript; charset=utf-8"],
    [".json", "application/json; charset=utf-8"],
    [".png", "image/png"],
    [".svg", "image/svg+xml"],
    [".woff2", "font/woff2"],
  ]);

  return new Promise((resolve, reject) => {
    const server = http.createServer((request, response) => {
      const requestPath = decodeURIComponent(new URL(request.url, WEB_URL).pathname);
      const relativePath = requestPath === "/" ? "index.html" : requestPath.slice(1);
      const filePath = path.resolve(root, relativePath);
      if (!filePath.startsWith(`${path.resolve(root)}${path.sep}`)) {
        response.writeHead(403).end("Forbidden");
        return;
      }

      fs.readFile(filePath, (error, contents) => {
        if (error) {
          response.writeHead(error.code === "ENOENT" ? 404 : 500).end(
            error.code === "ENOENT" ? "Not found" : "Unable to read Knocklet files",
          );
          return;
        }
        response.writeHead(200, {
          "Cache-Control": "no-store",
          "Content-Type": contentTypes.get(path.extname(filePath)) ?? "application/octet-stream",
        });
        response.end(contents);
      });
    });
    server.once("error", reject);
    server.listen(WEB_PORT, "127.0.0.1", () => resolve(server));
  });
}

async function waitForApi(timeoutMilliseconds = 30000) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(API_URL);
      if (response.ok && (await response.json()).status === "ok") return;
    } catch {
      // The runtime is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error("The local API did not start within 30 seconds.");
}

function showWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  app.dock?.show();
  mainWindow.show();
  mainWindow.focus();
}

function createWindow() {
  mainWindow = new BrowserWindow({
    backgroundColor: "#000000",
    height: 820,
    minHeight: 640,
    minWidth: 860,
    show: false,
    title: "Knocklet",
    width: 1280,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.on("close", (event) => {
    if (quitting) return;
    event.preventDefault();
    mainWindow.hide();
    app.dock?.hide();
  });
  mainWindow.once("ready-to-show", showWindow);
  mainWindow.loadURL(WEB_URL).catch((error) => stopAfterRuntimeFailure("web", error));
}

function createTray() {
  const iconPath = app.isPackaged
    ? path.join(process.resourcesPath, "menuTemplate.png")
    : path.join(__dirname, "../assets/menuTemplate.png");
  const icon = nativeImage.createFromPath(iconPath);
  if (icon.isEmpty()) throw new Error(`Menu icon could not be loaded from ${iconPath}`);
  icon.setTemplateImage(true);
  tray = new Tray(icon);
  tray.setToolTip("Knocklet");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Open Knocklet", click: showWindow },
      { type: "separator" },
      {
        label: "Quit Knocklet",
        click: () => {
          quitting = true;
          app.quit();
        },
      },
    ]),
  );
}

async function start() {
  const runtimeDirectory = packagedPath("runtime");
  const runtime = path.join(runtimeDirectory, "knocklet-runtime");
  const webRoot = packagedPath("web");
  const logDirectory = path.join(app.getPath("userData"), "logs");
  const logPath = path.join(logDirectory, "desktop.log");
  fs.mkdirSync(logDirectory, { recursive: true });
  const logDescriptor = fs.openSync(logPath, "a");
  const environment = runtimeEnvironment();

  runMigrations(runtime, environment, logDescriptor, logPath);
  apiProcess = startRuntime(runtime, "serve", environment, logDescriptor);
  workerProcess = startRuntime(runtime, "worker", environment, logDescriptor);
  webServer = await startStaticServer(webRoot);
  await waitForApi();
  createWindow();
  createTray();
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", showWindow);
  app.on("activate", showWindow);
  app.on("before-quit", () => {
    quitting = true;
    webServer?.close();
    stopRuntime(apiProcess);
    stopRuntime(workerProcess);
  });
  app.on("window-all-closed", () => {});
  app.whenReady().then(start).catch((error) => {
    dialog.showErrorBox("Knocklet could not start", error.message);
    quitting = true;
    app.quit();
  });
}
