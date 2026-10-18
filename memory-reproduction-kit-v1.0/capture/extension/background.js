// Project capture: explicit project inventory, validated timestamps, auditable results.
// No ChatGPT page needs to stay open. Cookies stay in the browser; token stays in memory.
const SERVER = 'http://127.0.0.1:8765';
const CHATGPT = 'https://chatgpt.com';
const CAPTURE_VERSION = 2;
const get = async (k) => (await chrome.storage.local.get(k))[k];
const set = (v) => chrome.storage.local.set(v);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const eventError = (stage, error, extra = {}) => ({stage, error: String(error.message || error), ...extra});

function epoch(value) {
  if (typeof value === 'string' && /^\d+(\.\d+)?$/.test(value)) value = Number(value);
  if (typeof value === 'number') {
    if (!Number.isFinite(value) || value <= 0) throw Error('invalid numeric timestamp');
    return value > 100000000000 ? value / 1000 : value;
  }
  if (typeof value !== 'string' || !/^\d{4}-\d\d-\d\dT.*(?:Z|[+-]\d\d:\d\d)$/.test(value)) throw Error('timestamp must be epoch or timezone-qualified ISO');
  const n = Date.parse(value) / 1000;
  if (!Number.isFinite(n) || n <= 0) throw Error('invalid ISO timestamp');
  return n;
}
async function stage(name) { await set({run: {stage: name, heartbeat: Date.now()}}); }
async function wakefulSleep(ms, label) {
  for (let left = ms; left > 0; left -= 10000) {
    await stage(label); await sleep(Math.min(left, 10000));
  }
}
async function server(method, path, body) {
  const r = await fetch(SERVER + path, {method,
    headers: body ? {'Content-Type': 'application/json'} : {},
    body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(120000)});
  if (!r.ok) throw Error(`local ${path}: HTTP ${r.status}`);
  return r.json();
}
async function api(path, token) {
  for (let attempt = 0; ; attempt++) {
    const r = await fetch(CHATGPT + path, {credentials: 'include', headers: {Authorization: 'Bearer ' + token}, signal: AbortSignal.timeout(60000)});
    if (r.status === 429 && attempt < 8) {
      const requested = Number(r.headers.get('Retry-After'));
      await wakefulSleep((Number.isFinite(requested) && requested > 0 ? Math.min(requested, 300) : 30 * (attempt + 1)) * 1000, 'rate limited');
      continue;
    }
    if (!r.ok) throw Error(`${path.split('?')[0]}: HTTP ${r.status}`);
    return r.json();
  }
}
function pageItems(j) {
  if (!j || !Array.isArray(j.items)) throw Error('unsupported project response: expected items array');
  if (j.items.some(x => !x || typeof x.id !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(x.id))) throw Error('invalid conversation ID in project listing');
  return j.items;
}
async function listProject(projectId, token) {
  const rows = new Map(), cursors = new Set();
  let cursor = '0', pages = 0;
  while (cursor !== null) {
    if (cursors.has(String(cursor)) || pages >= 1000) throw Error('repeated cursor or page limit: inventory incomplete');
    cursors.add(String(cursor));
    const j = await api(`/backend-api/gizmos/${encodeURIComponent(projectId)}/conversations?cursor=${encodeURIComponent(cursor)}`, token);
    const items = pageItems(j); pages++;
    for (const item of items) {
      if (item.gizmo_id && item.gizmo_id !== projectId) throw Error('project ID mismatch in listing');
      const old = rows.get(item.id);
      if (!old || epoch(item.update_time) > epoch(old.update_time)) rows.set(item.id, {...item, _capture_project_id: projectId});
    }
    const next = j.next_cursor !== undefined ? j.next_cursor : j.cursor;
    if (next != null && typeof next !== 'string' && typeof next !== 'number') throw Error('unsupported cursor type');
    if (j.has_more === true && (next == null || next === '')) throw Error('has_more without cursor: inventory incomplete');
    if (next != null && next !== '' && items.length === 0) throw Error('empty page with continuation: inventory incomplete');
    cursor = next == null || next === '' ? null : String(next);
  }
  return {rows: [...rows.values()], pages};
}
function validateDetail(conv, meta) {
  const cid = conv && (conv.conversation_id || conv.id);
  if (cid !== meta.id) throw Error('listing/detail ID mismatch');
  if (conv.gizmo_id && conv.gizmo_id !== meta._capture_project_id) throw Error('detail is outside selected project');
  if (!conv.mapping || typeof conv.mapping !== 'object' || Array.isArray(conv.mapping) || !conv.current_node || !conv.mapping[conv.current_node]) throw Error('incomplete conversation tree');
  if (epoch(conv.update_time) + .001 < epoch(meta.update_time)) throw Error('detail snapshot older than listing; retry needed');
}
async function setBadge(error) {
  await chrome.action.setBadgeText({text: error ? '!' : ''});
  await chrome.action.setBadgeBackgroundColor({color: '#c62828'});
  const last = await get('lastSuccess');
  await chrome.action.setTitle({title: `Project Chat Capture\nLast complete run: ${last ? new Date(last).toLocaleString() : 'never'}${error ? '\nPartial/failed — see failure list' : ''}`});
}
async function runSync() {
  const startedAt = new Date().toISOString();
  const errors = [], inventories = [], listing = [];
  const summary = {listed: 0, fetched: 0, stored: 0, unchanged: 0};
  let config = null, kind = null;
  try {
    await stage('checking local settings');
    config = await server('GET', '/config');
    if (config.capture_version !== CAPTURE_VERSION || !Array.isArray(config.project_ids) || !config.project_ids.length || config.project_ids.some(x => typeof x !== 'string' || !/^g-p-[a-zA-Z0-9-]+$/.test(x))) throw Error('missing/invalid explicit project whitelist or listener version');
    const {ids} = await server('GET', '/state');
    if (!ids || typeof ids !== 'object' || Array.isArray(ids)) throw Error('invalid local index response');
    await stage('checking browser login');
    const r = await fetch(CHATGPT + '/api/auth/session', {credentials: 'include', signal: AbortSignal.timeout(30000)});
    const session = await r.json();
    if (!r.ok || typeof session.accessToken !== 'string' || !session.accessToken) {
      kind = 'login'; throw Error(`no usable ChatGPT session (HTTP ${r.status})`);
    }
    const token = session.accessToken;
    for (const projectId of [...new Set(config.project_ids)]) {
      await stage('listing selected project');
      try {
        const result = await listProject(projectId, token);
        listing.push(...result.rows); inventories.push({project_id: projectId, complete: true, listed: result.rows.length, pages: result.pages});
      } catch (e) {
        errors.push(eventError('inventory', e, {project_id: projectId}));
        inventories.push({project_id: projectId, complete: false});
      }
    }
    if (!listing.length && Object.keys(ids).length && inventories.every(x => x.complete)) errors.push(eventError('inventory', 'empty inventory despite existing local conversations; explicit review required'));
    const seen = new Set();
    for (const meta of listing) {
      if (seen.has(meta.id)) { errors.push(eventError('inventory', 'same conversation listed in multiple selected projects', {id: meta.id})); continue; }
      seen.add(meta.id); summary.listed++;
      try {
        const updated = epoch(meta.update_time);
        if (Object.hasOwn(ids, meta.id) && typeof ids[meta.id] === 'number' && ids[meta.id] >= updated - .001) { summary.unchanged++; continue; }
        await stage(`fetching selected conversation ${summary.fetched + 1}`);
        if (summary.fetched) await sleep(2000);
        const conversation = await api(`/backend-api/conversation/${encodeURIComponent(meta.id)}`, token);
        validateDetail(conversation, meta); summary.fetched++;
        const receipt = await server('POST', '/conversations', {items: [{meta, conversation}]});
        if (!Array.isArray(receipt.accepted_ids) || !receipt.accepted_ids.includes(meta.id) || !Array.isArray(receipt.errors) || receipt.errors.length) throw Error('local store rejected conversation');
        summary.stored++;
      } catch (e) { errors.push(eventError('conversation', e, {id: meta.id, project_id: meta._capture_project_id})); }
    }
  } catch (e) { errors.push(eventError('run', e)); }
  const complete = errors.length === 0 && config !== null && inventories.length === new Set(config.project_ids).size && inventories.every(x => x.complete);
  const report = {started_at: startedAt, finished_at: new Date().toISOString(), complete, inventories, summary, errors,
    listing: listing.map(({id, is_archived, is_starred}) => ({id, is_archived, is_starred}))};
  try {
    const receipt = await server('POST', '/sync-done', report);
    if (report.complete && receipt.complete !== true) throw Error('local report/commit not confirmed complete');
  }
  catch (e) { errors.push(eventError('report', e)); report.complete = false; }
  const error = errors.length ? `${errors.length} failure(s): ${errors[0].stage}: ${errors[0].error}` : null;
  await set({lastFinished: Date.now(), lastSummary: summary, lastError: error, lastErrorKind: kind, lastReport: report, run: null});
  if (report.complete) await set({lastSuccess: Date.now()});
  await setBadge(error);
  return report;
}
let running = null;
async function maybeSync(interval) {
  if (running) return running;
  const run = await get('run');
  if (run && Date.now() - run.heartbeat < 180000) return;
  if (Date.now() - ((await get('lastFinished')) || 0) < interval) return;
  running = runSync().finally(() => { running = null; }); return running;
}
function ensureAlarm() { chrome.alarms.create('tick', {periodInMinutes: 30}); }
chrome.runtime.onInstalled.addListener(ensureAlarm);
chrome.runtime.onStartup.addListener(ensureAlarm);
chrome.alarms.onAlarm.addListener(a => { if (a.name === 'tick') maybeSync(30 * 60000); });
chrome.runtime.onMessage.addListener(msg => {
  if (msg.type === 'page-loaded') maybeSync(10 * 60000);
  if (msg.type === 'sync-now') maybeSync(0);
});
