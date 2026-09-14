const { contextBridge, ipcRenderer, shell } = require('electron');

contextBridge.exposeInMainWorld('desktop', {
  openExternal: (url) => shell.openExternal(url),
  fetchBooksXml: (url) => ipcRenderer.invoke('fetch-books-xml', url)
});
