const pageSize = 6;
const storageKey = 'lumen.microservices.config';
const legacyStorageKey = 'lumen.books.service';
const services = [
  { id: 'login', name: 'Login', port: 5000 },
  { id: 'books', name: 'Books', port: 5001 },
  { id: 'users', name: 'Users', port: 5002 },
  { id: 'authors', name: 'Authors', port: 5003 },
  { id: 'orders', name: 'Pedidos', port: 5004 },
  { id: 'payments', name: 'Pagos', port: 5005 }
];
const state = { books: [], page: 1, config: loadConfig(), serviceStates: {} };
const elements = {
  grid: document.querySelector('#booksGrid'), status: document.querySelector('#status'), page: document.querySelector('#pageIndicator'),
  previous: document.querySelector('#previousButton'), next: document.querySelector('#nextButton'), dialog: document.querySelector('#settingsDialog'),
  form: document.querySelector('#settingsForm'), serviceFields: document.querySelector('#serviceUrlFields'),
  catalogEndpoint: document.querySelector('#catalogEndpoint'), nav: document.querySelector('#servicesNav'), error: document.querySelector('#settingsError')
};

function defaultConfig() {
  return { services: Object.fromEntries(services.map(service => [service.id, `http://localhost:${service.port}`])), catalogEndpoint: '/api/books' };
}

function loadConfig() {
  const defaults = defaultConfig();
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    if (saved?.services) return { services: { ...defaults.services, ...saved.services }, catalogEndpoint: saved.catalogEndpoint || defaults.catalogEndpoint };
    const legacy = JSON.parse(localStorage.getItem(legacyStorageKey));
    if (legacy?.host) {
      defaults.services.books = (/^https?:\/\//i.test(legacy.host) ? legacy.host : `http://${legacy.host}`).replace(/\/$/, '');
      defaults.catalogEndpoint = legacy.endpoint || defaults.catalogEndpoint;
    }
  } catch { /* Use local defaults if saved settings are malformed. */ }
  return defaults;
}

function showStatus(message, kind = '') { elements.status.textContent = message; elements.status.className = `status ${kind}`; }

function normalizeBaseUrl(value) {
  const url = new URL(value.trim());
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Usa una URL HTTP o HTTPS sin credenciales.');
  url.pathname = url.pathname.replace(/\/$/, '');
  url.search = '';
  url.hash = '';
  return url.toString().replace(/\/$/, '');
}

function serviceUrl(id, endpoint = '') {
  const base = new URL(normalizeBaseUrl(state.config.services[id]));
  const suffix = endpoint.replace(/^\/+/, '');
  base.pathname = `${base.pathname.replace(/\/$/, '')}/${suffix}`.replace(/\/$/, '') || '/';
  return base.toString();
}

function createServiceControls() {
  elements.nav.replaceChildren();
  elements.serviceFields.replaceChildren();
  for (const service of services) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'service-link'; button.dataset.service = service.id;
    button.title = `Abrir ${service.name} en el navegador`;
    button.setAttribute('aria-label', `Abrir ${service.name}; estado sin comprobar`);
    button.innerHTML = '<span class="service-light state-checking" aria-hidden="true"></span><span class="service-link-name"></span><span class="service-link-port"></span>';
    button.querySelector('.service-link-name').textContent = service.name;
    button.querySelector('.service-link-port').textContent = `:${service.port}`;
    button.addEventListener('click', () => window.desktop.openService(state.config.services[service.id]).catch(error => showStatus(error.message, 'error')));
    elements.nav.append(button);

    const label = document.createElement('label'); label.className = 'service-url-field'; label.htmlFor = `serviceUrl-${service.id}`;
    const name = document.createElement('span'); name.textContent = `${service.name} · puerto ${service.port}`;
    const input = document.createElement('input');
    input.id = `serviceUrl-${service.id}`; input.name = service.id; input.type = 'url'; input.required = true;
    input.autocomplete = 'url'; input.spellcheck = false; input.value = state.config.services[service.id];
    input.placeholder = `http://localhost:${service.port}`;
    label.append(name, input); elements.serviceFields.append(label);
  }
  elements.catalogEndpoint.value = state.config.catalogEndpoint;
}

function setServiceState(id, result) {
  state.serviceStates[id] = result.state;
  const button = elements.nav.querySelector(`[data-service="${id}"]`);
  if (!button) return;
  const labels = { online: 'Conexión activa', degraded: 'Servicio con errores', offline: 'Sin conexión', checking: 'Comprobando conexión' };
  const name = button.querySelector('.service-link-name').textContent;
  button.title = `${name}: ${labels[result.state] || labels.offline}${result.status ? ` (HTTP ${result.status})` : ''}`;
  button.setAttribute('aria-label', `Abrir ${name}; ${labels[result.state] || labels.offline}`);
  button.querySelector('.service-light').className = `service-light state-${result.state}`;
}

let healthCheckRunning = false;
async function checkServices() {
  if (healthCheckRunning) return;
  healthCheckRunning = true;
  try {
    await Promise.all(services.map(async service => {
      setServiceState(service.id, { state: 'checking' });
      try { setServiceState(service.id, await window.desktop.checkService(service.id, state.config.services[service.id])); }
      catch { setServiceState(service.id, { state: 'offline' }); }
    }));
  } finally { healthCheckRunning = false; }
}
async function loadBooks() {
  let url;
  try {
    const endpoint = elements.catalogEndpoint.value || state.config.catalogEndpoint;
    if (!endpoint.startsWith('/')) throw new Error('La ruta del catálogo debe comenzar con /.');
    url = serviceUrl('books', endpoint);
  } catch (error) { state.books = []; state.page = 1; render(); showStatus(error.message, 'error'); return; }
  state.books = []; state.page = 1; render(); showStatus('Cargando catálogo…');
  try {
    const response = await window.desktop.fetchBooks(url);
    if (response.format === 'json') state.books = normalizeJsonBooks(response.data);
    else {
      const xml = new DOMParser().parseFromString(response.data, 'application/xml');
      if (xml.querySelector('parsererror')) throw new Error('La respuesta no contiene XML válido.');
      state.books = [...xml.querySelectorAll('book, libro, item')].map(parseBook).filter(book => book.title);
    }
    render(); showStatus(state.books.length ? `${state.books.length} libros disponibles.` : 'El catálogo no contiene libros disponibles.', state.books.length ? 'success' : 'info');
  } catch (error) { render(); showStatus(`No se pudo cargar el catálogo: ${error.message}`, 'error'); }
}
function value(node, names) { for (const name of names) { const match = node.querySelector(`:scope > ${name}`); if (match?.textContent.trim()) return match.textContent.trim(); } return ''; }
function parseBook(node) {
  return { title: value(node, ['title', 'titulo', 'name', 'nombre']), authors: value(node, ['authors', 'autores', 'author', 'autor']), isbn: value(node, ['isbn', 'ISBN']), price: value(node, ['price', 'precio', 'cost']), image: value(node, ['image', 'imagen', 'photo', 'foto', 'cover', 'portada']) };
}
function normalizeJsonBooks(payload) {
  const books = Array.isArray(payload) ? payload : payload?.books || payload?.data?.books || [];
  if (!Array.isArray(books)) throw new Error('La respuesta JSON no contiene una lista de libros.');
  return books.map(book => ({
    title: book.title || book.titulo || book.name || '',
    authors: Array.isArray(book.authors) ? book.authors.join(', ') : (book.authors || book.author || ''),
    isbn: book.isbn || '',
    price: book.price ?? (book.price_cents != null ? (Number(book.price_cents) / 100).toFixed(2) : ''),
    image: book.image || book.cover || book.images?.[0]?.url || ''
  })).filter(book => book.title);
}
function render() {
  const totalPages = Math.max(1, Math.ceil(state.books.length / pageSize)); state.page = Math.min(state.page, totalPages);
  elements.grid.replaceChildren();
  state.books.slice((state.page - 1) * pageSize, state.page * pageSize).forEach((book, index) => elements.grid.append(createCard(book, index)));
  elements.page.textContent = `Página ${state.page} de ${totalPages}`; elements.previous.disabled = state.page <= 1; elements.next.disabled = state.page >= totalPages;
}
function createCard(book, index) {
  const card = document.createElement('article'); card.className = `book-card tone-${index % 4}`;
  const cover = document.createElement('div'); cover.className = 'book-cover';
  if (book.image) { const image = document.createElement('img'); image.src = book.image; image.alt = `Portada de ${book.title}`; image.onerror = () => { image.remove(); cover.append(initial(book.title)); }; cover.append(image); } else cover.append(initial(book.title));
  const details = document.createElement('div'); details.className = 'book-details';
  const title = document.createElement('h3'); title.textContent = book.title;
  const author = document.createElement('p'); author.className = 'author'; author.textContent = book.authors || 'Autor no indicado';
  const meta = document.createElement('div'); meta.className = 'book-meta'; meta.append(metaItem('ISBN', book.isbn || '—'), metaItem('PRECIO', book.price || '—'));
  details.append(title, author, meta); card.append(cover, details); return card;
}
function initial(title) { const span = document.createElement('span'); span.className = 'cover-initial'; span.textContent = title.charAt(0).toUpperCase() || '?'; return span; }
function metaItem(label, content) { const item = document.createElement('span'); item.innerHTML = `<small>${label}</small>`; const valueNode = document.createElement('b'); valueNode.textContent = content; item.append(valueNode); return item; }

document.querySelector('#settingsButton').addEventListener('click', () => { createServiceControls(); elements.error.textContent = ''; elements.dialog.showModal(); });
document.querySelector('#closeDialogButton').addEventListener('click', () => elements.dialog.close());
document.querySelector('#resetSettingsButton').addEventListener('click', () => { state.config = defaultConfig(); createServiceControls(); });
elements.form.addEventListener('submit', event => {
  event.preventDefault();
  try {
    const serviceUrls = Object.fromEntries(services.map(service => [service.id, normalizeBaseUrl(elements.form.elements.namedItem(service.id).value)]));
    const endpoint = elements.catalogEndpoint.value.trim();
    if (!endpoint.startsWith('/')) throw new Error('La ruta del catálogo debe comenzar con /.');
    state.config = { services: serviceUrls, catalogEndpoint: endpoint };
    localStorage.setItem(storageKey, JSON.stringify(state.config));
    elements.dialog.close(); createServiceControls(); checkServices(); loadBooks();
  } catch (error) { elements.error.textContent = error.message || 'Revisa las URLs de los microservicios.'; }
});
document.querySelector('#reloadButton').addEventListener('click', loadBooks);
elements.previous.addEventListener('click', () => { if (state.page > 1) { state.page -= 1; render(); } });
elements.next.addEventListener('click', () => { if (state.page < Math.ceil(state.books.length / pageSize)) { state.page += 1; render(); } });
createServiceControls(); render(); loadBooks(); checkServices(); setInterval(checkServices, 15000);
