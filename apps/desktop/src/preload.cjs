const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("knockletUpdates", {
  check: () => ipcRenderer.invoke("updates:check"),
  download: () => ipcRenderer.invoke("updates:download"),
  getState: () => ipcRenderer.invoke("updates:get-state"),
  install: () => ipcRenderer.invoke("updates:install"),
  subscribe(listener) {
    if (typeof listener !== "function") {
      throw new TypeError("An update-state listener is required.");
    }
    const handler = (_event, state) => listener(state);
    ipcRenderer.on("updates:state", handler);
    return () => ipcRenderer.removeListener("updates:state", handler);
  },
});
