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

function parseHttpUrl(value) {
  let url;
  try { url = new URL(value); } catch { throw new Error('La URL del servicio no es válida.'); }
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Solo se permiten URLs HTTP o HTTPS.');
  return url;
}

ipcMain.handle('open-service', async (event, value) => {
  const url = parseHttpUrl(value);
  await shell.openExternal(url.toString());
  return true;
});

ipcMain.handle('check-service', async (event, id, value) => {
  const base = parseHttpUrl(value);
  base.pathname = `${base.pathname.replace(/\/$/, '')}/health`;
  base.search = '';
  base.hash = '';
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2500);
  try {
    const response = await fetch(base, { headers: { Accept: 'application/json, application/xml, text/xml' }, signal: controller.signal });
    return { id, state: response.status === 200 ? 'online' : 'degraded', status: response.status };
  } catch {
    return { id, state: 'offline', status: null };
  } finally {
    clearTimeout(timeout);
  }
});

ipcMain.handle('fetch-books', async (event, value) => {
  const url = parseHttpUrl(value);
  const response = await fetch(url, { headers: { Accept: 'application/json, application/xml, text/xml' } });
  if (!response.ok) throw new Error(`El servicio respondió con HTTP ${response.status}.`);
  const contentType = response.headers.get('content-type') || '';
  const text = await response.text();
  if (contentType.includes('json') || /^\s*[\[{]/.test(text)) {
    try { return { format: 'json', data: JSON.parse(text) }; }
    catch { throw new Error('El servicio respondió JSON inválido.'); }
  }
  return { format: 'xml', data: text };
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
