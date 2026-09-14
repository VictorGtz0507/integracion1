const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('node:path');

function createWindow() {
  const window = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 760,
    minHeight: 620,
    backgroundColor: '#f6f8f7',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  window.loadFile('index.html');
}

ipcMain.handle('fetch-books-xml', async (event, url) => {
  if (typeof url !== 'string' || !/^https?:\/\//i.test(url)) throw new Error('La URL del servicio no es válida.');
  const response = await fetch(url, { headers: { Accept: 'application/xml, text/xml' } });
  if (!response.ok) throw new Error(`El servicio respondió con HTTP ${response.status}.`);
  const contentType = response.headers.get('content-type') || '';
  const text = await response.text();
  if (contentType.includes('json') || /^\s*[\[{]/.test(text)) throw new Error('El servicio respondió JSON. Esta aplicación acepta únicamente XML.');
  return text;
});

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});
app.on('web-contents-created', (event, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
});
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
