ADMIN_HTML = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Proxy Provider Admin</title>
  <style>
    :root {
      --bg: #101315;
      --panel: #171c20;
      --panel-2: #1f272d;
      --text: #eef3f1;
      --muted: #9fb0aa;
      --accent: #f2b84b;
      --bad: #ff6b6b;
      --good: #5fd19b;
      --line: #2d383f;
      --code: #0b0e10;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: radial-gradient(circle at top left, #26351f 0, transparent 28rem),
                  radial-gradient(circle at top right, #352817 0, transparent 24rem),
                  var(--bg);
      color: var(--text);
    }
    header { padding: 28px clamp(18px, 4vw, 56px) 12px; }
    h1 { margin: 0 0 8px; font-size: clamp(28px, 5vw, 54px); letter-spacing: -0.05em; }
    p { color: var(--muted); line-height: 1.5; }
    main { display: grid; grid-template-columns: 360px 1fr; gap: 18px; padding: 18px clamp(18px, 4vw, 56px) 48px; }
    section, .card { background: color-mix(in srgb, var(--panel) 94%, transparent); border: 1px solid var(--line); border-radius: 18px; padding: 18px; box-shadow: 0 18px 60px rgba(0,0,0,.28); }
    label { display:block; margin: 12px 0 6px; color: var(--muted); font-size: 13px; }
    input, select {
      width: 100%; padding: 11px 12px; border-radius: 12px; border: 1px solid var(--line);
      background: var(--code); color: var(--text); outline: none;
    }
    button {
      border: 0; border-radius: 999px; padding: 11px 16px; background: var(--accent); color: #171007;
      font-weight: 700; cursor: pointer; margin-top: 14px;
    }
    button.secondary { background: var(--panel-2); color: var(--text); border: 1px solid var(--line); }
    .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
    .status { font-size: 13px; color: var(--muted); margin-top: 10px; }
    .pill { display:inline-flex; padding: 4px 9px; border-radius: 999px; background: var(--panel-2); color: var(--muted); font-size: 12px; margin: 2px; }
    .pill.good { color: var(--good); }
    .pill.bad { color: var(--bad); }
    .logs { display: grid; gap: 12px; }
    details { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 12px; }
    summary { cursor: pointer; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    pre { white-space: pre-wrap; word-break: break-word; background: var(--code); border: 1px solid var(--line); border-radius: 12px; padding: 12px; max-height: 420px; overflow: auto; }
    .grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
    .chain { border-color: color-mix(in srgb, var(--accent) 45%, var(--line)); }
    .route-record { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--line); }
    .warn { color: var(--accent); }
    @media (max-width: 980px) { main { grid-template-columns: 1fr; } .grid3 { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>Proxy Provider Admin</h1>
    <p>Логи маршрутов, фактические payload до модели и минимальная настройка дополнительных OpenAI-compatible providers.</p>
  </header>
  <main>
    <aside class="card">
      <h2>Доступ</h2>
      <label>Admin key</label>
      <input id="adminKey" type="password" placeholder="PROXY_PROVIDER_API_KEY или ADMIN_UI_API_KEY" />
      <button onclick="saveKey()">Сохранить ключ</button>
      <p class="status" id="authStatus"></p>

      <h2>Новый provider</h2>
      <label>Model alias в Open WebUI</label>
      <input id="providerId" placeholder="my-provider" />
      <label>Название</label>
      <input id="providerLabel" placeholder="My Provider" />
      <label>OpenAI-compatible base URL</label>
      <input id="providerBaseUrl" placeholder="https://api.example.com/v1" />
      <label>API key</label>
      <input id="providerApiKey" type="password" placeholder="sk-..." />
      <label>Upstream model</label>
      <input id="providerModel" placeholder="model-name" />
      <button onclick="saveProvider()">Добавить / обновить</button>
      <p class="status">Дополнительные providers работают как direct OpenAI-compatible маршруты. Для приватного режима используйте `yandex-private`.</p>

      <h2>Проверки</h2>
      <button class="secondary" onclick="loadAll()">Обновить</button>
      <p class="status" id="health"></p>
      <div id="providers"></div>
    </aside>

    <section>
      <div class="row">
        <h2 style="margin-right:auto">Request logs</h2>
        <select id="limit" style="width:120px" onchange="loadLogs()">
          <option>50</option>
          <option>100</option>
          <option>200</option>
        </select>
        <button class="secondary" onclick="loadLogs()">Refresh</button>
      </div>
      <p class="status">Логи сгруппированы по `request_id`. Для `yandex-private` главным является блок <b>Фактически ушло в модель</b>: он берётся из `route=internal-yandex` после anonymizer. `route=private` — это только hop до локального anon-proxy.</p>
      <p class="status">Если `content_logged=false`, message content намеренно скрыт. Для raw/preprocessed payload включите `AUDIT_LOG_CONTENT=true` и пересоздайте `proxy-provider`.</p>
      <div class="logs" id="logs"></div>
    </section>
  </main>
  <script>
    const keyInput = document.getElementById('adminKey');
    keyInput.value = localStorage.getItem('proxyAdminKey') || '';
    function adminHeaders() { return {'X-Admin-Key': keyInput.value}; }
    function saveKey() {
      localStorage.setItem('proxyAdminKey', keyInput.value);
      document.getElementById('authStatus').textContent = 'Ключ сохранён локально в браузере.';
      loadAll();
    }
    async function api(path, options = {}) {
      const response = await fetch(path, {...options, headers: {...adminHeaders(), ...(options.headers || {})}});
      if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
      return response.json();
    }
    function pretty(value) { return JSON.stringify(value ?? null, null, 2); }
    async function loadHealth() {
      const health = await fetch('/health').then(r => r.json());
      document.getElementById('health').innerHTML =
        `health=${health.status}, yandex_configured=${health.yandex_configured}, audit_log_content=${health.audit_log_content}`;
    }
    async function loadProviders() {
      const data = await api('/admin/api/providers');
      document.getElementById('providers').innerHTML = data.providers.map(p =>
        `<div class="pill ${p.enabled ? 'good' : 'bad'}">${p.id} -> ${p.model} (${p.api_key_set ? 'key set' : 'no key'})</div>`
      ).join('') || '<p class="status">Дополнительных providers нет.</p>';
    }
    async function saveProvider() {
      await api('/admin/api/providers', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          id: document.getElementById('providerId').value,
          label: document.getElementById('providerLabel').value,
          base_url: document.getElementById('providerBaseUrl').value,
          api_key: document.getElementById('providerApiKey').value,
          model: document.getElementById('providerModel').value,
          enabled: true
        })
      });
      await loadProviders();
      alert('Provider сохранён. Он появится в /v1/models.');
    }
    async function loadLogs() {
      const limit = document.getElementById('limit').value;
      const data = await api(`/admin/api/logs?limit=${limit}`);
      const groups = [];
      const byId = new Map();
      for (const item of data.logs) {
        if (!byId.has(item.request_id)) {
          const group = {request_id: item.request_id, rows: []};
          byId.set(item.request_id, group);
          groups.push(group);
        }
        byId.get(item.request_id).rows.push(item);
      }
      document.getElementById('logs').innerHTML = groups.map(group => renderGroup(group)).join('');
    }
    function routeTitle(route) {
      if (route === 'private') return 'Open WebUI -> proxy-provider -> local anon-proxy';
      if (route === 'internal-yandex') return 'local anon-proxy -> Yandex: ACTUAL MODEL PAYLOAD';
      if (route === 'direct') return 'proxy-provider -> Yandex direct: ACTUAL MODEL PAYLOAD';
      if (route === 'configured-direct') return 'proxy-provider -> configured provider: ACTUAL MODEL PAYLOAD';
      return route;
    }
    function actualModelRow(rows) {
      return rows.find(item => item.route === 'internal-yandex')
        || rows.find(item => item.route === 'direct')
        || rows.find(item => item.route === 'configured-direct')
        || null;
    }
    function latestRow(rows) {
      return rows.slice().sort((a, b) => b.ts - a.ts)[0];
    }
    function renderGroup(group) {
      const rows = group.rows.slice().sort((a, b) => a.ts - b.ts);
      const head = latestRow(rows);
      const actual = actualModelRow(rows);
      const ts = new Date(head.ts * 1000).toLocaleString();
      const hasPrivate = rows.some(item => item.route === 'private');
      const actualPayload = actual ? actual.upstream_json : {warning: 'No actual model hop recorded yet. If this is a private request, wait for route=internal-yandex or check anon-proxy logs.'};
      const routeRows = rows.map(renderRouteRow).join('');
      return `<details class="chain">
          <summary>
            <span class="pill">${ts}</span>
            <span class="pill">request_id=${group.request_id}</span>
            <span class="pill ${hasPrivate ? 'good' : ''}">${hasPrivate ? 'private chain' : 'direct chain'}</span>
            <span class="pill ${head.status >= 400 ? 'bad' : 'good'}">last_status=${head.status}</span>
            <span class="pill">hops=${rows.length}</span>
            <span class="pill">content_logged=${head.content_logged}</span>
          </summary>
          <h3>Фактически ушло в модель</h3>
          <p class="status ${actual ? '' : 'warn'}">${actual ? routeTitle(actual.route) : 'Фактический model-hop не найден в выбранном лимите логов.'}</p>
          <pre>${pretty(actualPayload)}</pre>
          ${routeRows}
        </details>`;
    }
    function renderRouteRow(item) {
      const ts = new Date(item.ts * 1000).toLocaleString();
      return `<div class="route-record">
          <div class="row">
            <span class="pill">${ts}</span>
            <span class="pill">${item.provider}</span>
            <span class="pill">${item.route}</span>
            <span class="pill">${routeTitle(item.route)}</span>
            <span class="pill">${item.model_alias}</span>
            <span class="pill ${item.status >= 400 ? 'bad' : 'good'}">${item.status}</span>
            <span class="pill">stream=${item.stream}</span>
          </div>
          <div class="grid3">
            <div><h3>Что пришло</h3><pre>${pretty(item.incoming_json)}</pre></div>
            <div><h3>${item.route === 'private' ? 'Что ушло в local anon-proxy' : 'Что ушло дальше / в модель'}</h3><pre>${pretty(item.upstream_json)}</pre></div>
            <div><h3>Ответ / stream sample</h3><pre>${pretty(item.response_json || item.error)}</pre></div>
          </div>
        </div>`;
    }
    async function loadAll() {
      try {
        await loadHealth();
        await loadProviders();
        await loadLogs();
      } catch (error) {
        document.getElementById('authStatus').textContent = `Ошибка: ${error.message}`;
      }
    }
    loadAll();
  </script>
</body>
</html>
"""
