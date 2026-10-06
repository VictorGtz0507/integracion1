const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('desktop', {
  openService: (url) => ipcRenderer.invoke('open-service', url),
  checkService: (id, url) => ipcRenderer.invoke('check-service', id, url),
  fetchBooks: (url) => ipcRenderer.invoke('fetch-books', url)
});
