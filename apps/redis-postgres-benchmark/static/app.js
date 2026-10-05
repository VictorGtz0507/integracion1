const $ = (selector) => document.querySelector(selector);
const message = $('#message');

function formatBytes(bytes) {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index += 1; }
  return `${value.toFixed(2)} ${units[index]}`;
}

function setMessage(text, kind = '') {
  message.textContent = text;
  message.className = `message ${kind}`;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function setConnection(id, connected) {
  const element = $(id);
  element.textContent = connected ? 'Conectado' : 'Desconectado';
  element.className = `connection-state ${connected ? 'ready' : 'down'}`;
}

async function refreshStatus() {
  try {
    const status = await requestJson('/api/status');
    setConnection('#pgState', Boolean(status.postgres));
    setConnection('#redisState', Boolean(status.redis));
    if (status.postgres) {
      $('#pgSize').textContent = `${status.postgres.database_mb.toFixed(2)} MB`;
      $('#bookCount').textContent = `Catálogo: ${status.postgres.book_count.toLocaleString('es')} libros`;
    } else $('#pgSize').textContent = 'Sin conexión';
    if (status.redis) {
      $('#redisMemory').textContent = `${status.redis.used_mb.toFixed(2)} MB`;
      $('#payloadSize').textContent = formatBytes(status.redis.payload_bytes);
      $('#redisLimit').textContent = status.redis.maxmemory_mb == null ? 'Límite Redis: sin configurar' : `Límite Redis: ${status.redis.maxmemory_mb.toFixed(2)} MB`;
      $('#cacheState').textContent = status.redis.cached ? `Caché: ${status.redis.cached_book_count.toLocaleString('es')} libros` : 'Caché: vacía';
    } else {
      $('#redisMemory').textContent = 'Sin conexión';
      $('#payloadSize').textContent = '—';
      $('#cacheState').textContent = 'Caché: no disponible';
    }
    if (status.errors.length) setMessage(status.errors.join(' '), 'error');
  } catch (error) {
    setMessage(error.message, 'error');
  }
}

function renderMetric(prefix, metric) {
  $(`#${prefix}Median`).textContent = metric.median_ms.toFixed(3);
  $(`#${prefix}Average`).textContent = `${metric.average_ms.toFixed(3)} ms`;
  $(`#${prefix}P95`).textContent = `${metric.p95_ms.toFixed(3)} ms`;
  if (prefix === 'pg') $(`#${prefix}Ops`).textContent = metric.operations_per_second.toLocaleString('es');
  if (prefix === 'redis') $(`#${prefix}Ops`).textContent = metric.operations_per_second.toLocaleString('es');
}

function renderBooks(books) {
  const body = $('#bookRows');
  body.replaceChildren();
  if (!books.length) {
    const row = document.createElement('tr');
    row.innerHTML = '<td colspan="5" class="empty-row">La consulta no devolvió libros.</td>';
    body.append(row);
    return;
  }
  for (const book of books) {
    const row = document.createElement('tr');
    const values = [book.title, book.isbn, (book.authors || []).join(', ') || '—', book.stock, book.price_cents == null ? '—' : `${(book.price_cents / 100).toFixed(2)}`];
    for (const value of values) {
      const cell = document.createElement('td');
      cell.textContent = value ?? '—';
      row.append(cell);
    }
    body.append(row);
  }
}

function renderBenchmark(result) {
  renderMetric('pg', result.postgres_direct);
  renderMetric('redis', result.redis_hit);
  $('#missMedian').textContent = result.redis_miss_fill.median_ms.toFixed(3);
  $('#missAverage').textContent = `${result.redis_miss_fill.average_ms.toFixed(3)} ms`;
  $('#missP95').textContent = `${result.redis_miss_fill.p95_ms.toFixed(3)} ms`;
  $('#missRuns').textContent = result.cache_miss_iterations;
  const slowest = Math.max(result.postgres_direct.median_ms, result.redis_hit.median_ms, 0.001);
  $('#pgBar').style.width = `${Math.max(2, result.postgres_direct.median_ms / slowest * 100)}%`;
  $('#redisBar').style.width = `${Math.max(2, result.redis_hit.median_ms / slowest * 100)}%`;
  $('#speedup').textContent = result.speedup == null ? '—' : `${result.speedup}×`;
  $('#verdict').textContent = result.speedup == null
    ? 'No fue posible calcular la diferencia de mediana.'
    : result.speedup >= 1
      ? `La lectura en caché fue ${result.speedup}× más rápida en esta ejecución secuencial.`
      : `En esta ejecución, Redis hit fue ${(1 / result.speedup).toFixed(2)}× más lento; revisa carga, red y tamaño del catálogo.`;
  $('#matchStatus').textContent = result.results_match ? 'Las dos rutas devolvieron los mismos libros' : 'Las respuestas difieren';
  $('#matchDot').className = `match-dot ${result.results_match ? 'ok' : 'bad'}`;
  $('#updatedAt').textContent = new Date().toLocaleTimeString('es');
  renderBooks(result.preview);
  refreshStatus();
}

$('#runButton').addEventListener('click', async () => {
  const button = $('#runButton');
  button.disabled = true;
  setMessage('Ejecutando lecturas secuenciales sobre el catálogo real…');
  try {
    const result = await requestJson('/api/benchmark', {
      method: 'POST',
      body: JSON.stringify({ iterations: Number($('#iterations').value) }),
    });
    renderBenchmark(result);
    setMessage(`Prueba terminada: ${result.book_count.toLocaleString('es')} libros, ${result.iterations} lecturas directas y ${result.cache_miss_iterations} pruebas de caché fría.`, 'success');
  } catch (error) {
    setMessage(error.message, 'error');
  } finally {
    button.disabled = false;
  }
});

$('#refreshButton').addEventListener('click', refreshStatus);
$('#clearCacheButton').addEventListener('click', async () => {
  try {
    await requestJson('/api/cache', { method: 'DELETE' });
    await refreshStatus();
    setMessage('La clave de caché de esta aplicación se borró. Los demás datos de Redis no se modificaron.', 'success');
  } catch (error) { setMessage(error.message, 'error'); }
});

refreshStatus();