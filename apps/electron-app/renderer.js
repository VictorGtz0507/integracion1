const pageSize = 6;
const storageKey = 'lumen.books.service';
const state = { books: [], page: 1, config: loadConfig() };
const elements = {
  grid: document.querySelector('#booksGrid'), status: document.querySelector('#status'), page: document.querySelector('#pageIndicator'),
  previous: document.querySelector('#previousButton'), next: document.querySelector('#nextButton'), dialog: document.querySelector('#settingsDialog'),
  form: document.querySelector('#settingsForm'), host: document.querySelector('#serviceHost'), endpoint: document.querySelector('#serviceEndpoint'), error: document.querySelector('#settingsError')
};

function loadConfig() {
  try { return JSON.parse(localStorage.getItem(storageKey)) || { host: '', endpoint: '' }; } catch { return { host: '', endpoint: '' }; }
}
function showStatus(message, kind = '') { elements.status.textContent = message; elements.status.className = `status ${kind}`; }
function buildUrl(config) {
  const host = config.host.trim().replace(/\/$/, '');
  const endpoint = config.endpoint.trim().replace(/^([^/])/, '/$1');
  if (!host || !endpoint) return '';
  return /^https?:\/\//i.test(host) ? `${host}${endpoint}` : `http://${host}${endpoint}`;
}
async function loadBooks() {
  const url = buildUrl(state.config);
  state.books = []; state.page = 1; render();
  if (!url) { showStatus('Configura la IP y el endpoint para cargar el catálogo.', 'info'); return; }
  showStatus('Cargando catálogo…');
  try {
    const text = await window.desktop.fetchBooksXml(url);
    const xml = new DOMParser().parseFromString(text, 'application/xml');
    if (xml.querySelector('parsererror')) throw new Error('La respuesta no contiene XML válido.');
    state.books = [...xml.querySelectorAll('book, libro, item')].map(parseBook).filter(book => book.title);
    render(); showStatus(state.books.length ? `${state.books.length} libros disponibles.` : 'El XML no contiene libros disponibles.', state.books.length ? 'success' : 'info');
  } catch (error) { render(); showStatus(`No se pudo cargar el catálogo: ${error.message}`, 'error'); }
}
function value(node, names) { for (const name of names) { const match = node.querySelector(`:scope > ${name}`); if (match?.textContent.trim()) return match.textContent.trim(); } return ''; }
function parseBook(node) {
  return { title: value(node, ['title', 'titulo', 'name', 'nombre']), authors: value(node, ['authors', 'autores', 'author', 'autor']), isbn: value(node, ['isbn', 'ISBN']), price: value(node, ['price', 'precio', 'cost']), image: value(node, ['image', 'imagen', 'photo', 'foto', 'cover', 'portada']) };
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

document.querySelector('#settingsButton').addEventListener('click', () => { elements.host.value = state.config.host; elements.endpoint.value = state.config.endpoint; elements.error.textContent = ''; elements.dialog.showModal(); });
document.querySelector('#closeDialogButton').addEventListener('click', () => elements.dialog.close());
document.querySelector('#clearSettingsButton').addEventListener('click', () => { elements.host.value = ''; elements.endpoint.value = ''; });
elements.form.addEventListener('submit', event => { event.preventDefault(); const config = { host: elements.host.value.trim(), endpoint: elements.endpoint.value.trim() }; if (!buildUrl(config)) { elements.error.textContent = 'Completa la IP o dominio y el endpoint.'; return; } localStorage.setItem(storageKey, JSON.stringify(config)); state.config = config; elements.dialog.close(); loadBooks(); });
document.querySelector('#reloadButton').addEventListener('click', loadBooks);
elements.previous.addEventListener('click', () => { if (state.page > 1) { state.page -= 1; render(); } });
elements.next.addEventListener('click', () => { if (state.page < Math.ceil(state.books.length / pageSize)) { state.page += 1; render(); } });
render(); loadBooks();
