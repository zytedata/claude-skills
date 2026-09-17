const THEME_IDS = new Set(['light', 'dark']);

const state = {
  currentView: 'field',
  selectedField: null,
  selectedPage: null,
  actions: {},
  schemaChanges: {},
  descriptions: {},
};

document.addEventListener('DOMContentLoaded', () => {
  if (typeof REVIEW_DATA === 'undefined') {
    document.getElementById('content').innerHTML = '<p>No data loaded.</p>';
    return;
  }
  REVIEW_DATA.fields.forEach(f => { state.descriptions[f.name] = f.description; });

  const saved = localStorage.getItem('theme');
  const prefersDark = matchMedia && matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = THEME_IDS.has(saved) ? saved : prefersDark ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', theme);
  document.body.setAttribute('data-theme', theme);

  setupViewToggle();
  setupThemeSwitcher();
  setupHeaderCopy();
  setupHeaderSend();
  setupFeedbackTrigger();
  setupHistory();
  renderChanges();
  renderSidebar();
  selectFirstItem();
  updateFeedback();
});

// ── View toggle ──
function setupViewToggle() {
  document.querySelectorAll('#view-toggle button').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#view-toggle button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.currentView = btn.dataset.view;
      renderSidebar();
      selectFirstItem();
      pushState();
    });
  });
}

// ── Theme (light/dark toggle) ──
function setupThemeSwitcher() {
  const btn = document.getElementById('theme-btn');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const root = document.documentElement;
    const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    document.body.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
  });
}

// ── Header copy ──
function setupHeaderCopy() {
  document.getElementById('header-copy').addEventListener('click', () => {
    const text = generateFeedbackText();
    navigator.clipboard.writeText(text).then(() => {
      const btn = document.getElementById('header-copy');
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
    });
  });
}

// ── Header actions ──
function setupHeaderSend() {
  if (typeof AGENT_URL === 'undefined') return;
  const approveBtn = document.getElementById('header-approve');
  const changesBtn = document.getElementById('header-request-changes');
  approveBtn.classList.remove('hidden');
  changesBtn.classList.remove('hidden');
  updateActionButtons();

  approveBtn.addEventListener('click', () => {
    const text = 'APPROVED\n' + generateFeedbackText();
    sendToAgent(text, approveBtn, 'Approve');
  });

  changesBtn.addEventListener('click', () => {
    sendToAgent(generateFeedbackText(), changesBtn, 'Request changes');
  });
}

function sendToAgent(text, btn, label) {
  clearStatusNotice();
  btn.disabled = true;
  btn.textContent = 'Sending\u2026';
  fetch(AGENT_URL, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: text })
    .then(r => {
      if (r.ok) {
        clearStatusNotice();
        btn.textContent = 'Sent!';
        btn.classList.add('sent');
        makeReadOnly();
      } else {
        showStatusNotice(`Could not send feedback (${r.status}). Please try again. If the problem persists, ask the agent to reopen the review.`);
        btn.textContent = 'Error';
        btn.disabled = false;
        setTimeout(() => { btn.textContent = label; }, 2000);
      }
    })
    .catch(() => {
      showStatusNotice('Could not send feedback. Please try again. If the problem persists, ask the agent to reopen the review.');
      btn.textContent = 'Error';
      btn.disabled = false;
      setTimeout(() => { btn.textContent = label; }, 2000);
    });
}

function hasCorrectionsOrFlags() {
  return Object.values(state.actions).some(a => a.type === 'correct' || a.type === 'flag');
}

function updateActionButtons() {
  if (typeof AGENT_URL === 'undefined') return;
  const changesBtn = document.getElementById('header-request-changes');
  const has = hasCorrectionsOrFlags();
  changesBtn.disabled = !has;
  changesBtn.style.opacity = has ? '1' : '0.4';
}

// ── Feedback dropdown ──
function setupFeedbackTrigger() {
  const link = document.getElementById('feedback-link');
  const dropdown = document.getElementById('feedback-dropdown');

  link.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('hidden');
  });

  document.addEventListener('click', (e) => {
    if (!dropdown.contains(e.target)) dropdown.classList.add('hidden');
  });

  dropdown.addEventListener('click', (e) => e.stopPropagation());
}

// ── Changes panel ──
function renderChanges() {
  if (typeof REVIEW_CHANGES === 'undefined' || !REVIEW_CHANGES.length) return;
  const panel = document.createElement('div');
  panel.id = 'changes-panel';
  panel.innerHTML = `<div class="changes-header"><span>Changes since last review</span><button onclick="this.closest('#changes-panel').remove()">&times;</button></div>
    <ul>${REVIEW_CHANGES.map(c => `<li>${escapeHtml(c)}</li>`).join('')}</ul>`;
  const content = document.getElementById('content');
  content.parentNode.insertBefore(panel, content);
}

function forceIframeLightMode(iframe) {
  try {
    const doc = iframe.contentDocument || iframe.contentWindow.document;
    if (!doc || !doc.head) return false;

    let meta = doc.querySelector('meta[name="color-scheme"]');
    if (meta) {
      meta.content = 'light';
    } else {
      meta = doc.createElement('meta');
      meta.name = 'color-scheme';
      meta.content = 'light';
      doc.head.appendChild(meta);
    }

    if (!doc.querySelector('#force-light-mode-style')) {
      const style = doc.createElement('style');
      style.id = 'force-light-mode-style';
      style.textContent = ':root { color-scheme: light !important; }';
      doc.head.appendChild(style);
    }

    return true;
  } catch (error) {
    const isExpectedCrossOrigin =
      error instanceof DOMException &&
      (error.name === 'SecurityError' || error.name === 'NotAllowedError');

    if (isExpectedCrossOrigin) {
      console.debug('Skipping iframe light-mode forcing due to cross-origin iframe');
      return false;
    }

    console.error('forceIframeLightMode failed unexpectedly', error);
    return false;
  }
}

// ── Sidebar ──
function renderSidebar() {
  const sidebar = document.getElementById('sidebar');
  const scrollTop = sidebar.scrollTop;
  sidebar.innerHTML = '';

  if (state.currentView === 'field') {
    const requested = REVIEW_DATA.fields.filter(f => f.source === 'requested');
    const discovered = REVIEW_DATA.fields.filter(f => f.source === 'discovered');

    const addFieldItem = (field, container) => {
      const el = document.createElement('div');
      el.className = 'sidebar-item';
      if (state.selectedField === field.name) el.classList.add('active');
      const change = state.schemaChanges[field.name]?.action;
      if (change === 'drop') el.classList.add('dropped');
      if (change === 'keep') el.classList.add('kept');
      el.innerHTML = `<span>${field.name}</span><span class="status-dot ${getFieldStatus(field.name)}"></span>`;
      el.addEventListener('click', () => {
        state.selectedField = field.name;
        renderSidebar();
        renderFieldView(field);
        pushState();
      });
      container.appendChild(el);
    };

    const addGroup = (label, fields) => {
      if (!fields.length) return;
      const details = document.createElement('details');
      details.className = 'sidebar-group';
      details.open = true;
      const summary = document.createElement('summary');
      summary.className = 'sidebar-group__header';
      summary.innerHTML = `<span class="sidebar-group__label">${label}</span><span class="sidebar-group__chevron" aria-hidden="true">⌄</span>`;
      const list = document.createElement('div');
      list.className = 'sidebar-group__list';
      details.appendChild(summary);
      details.appendChild(list);
      fields.forEach(f => addFieldItem(f, list));
      sidebar.appendChild(details);
    };

    addGroup('Requested', requested);
    addGroup('Discovered', discovered);
  } else {
    Object.keys(REVIEW_DATA.pages).forEach(pk => {
      const el = document.createElement('div');
      el.className = 'sidebar-item';
      if (state.selectedPage === pk) el.classList.add('active');
      el.innerHTML = `<span>${pk}</span><span class="status-dot ${getPageStatus(pk)}"></span>`;
      el.addEventListener('click', () => {
        state.selectedPage = pk;
        renderSidebar();
        renderPageView(pk);
        pushState();
      });
      sidebar.appendChild(el);
    });
  }
  sidebar.scrollTop = scrollTop;
}

function selectFirstItem() {
  if (state.currentView === 'field') {
    state.selectedField = REVIEW_DATA.fields[0]?.name;
    if (state.selectedField) renderFieldView(REVIEW_DATA.fields[0]);
  } else {
    const k = Object.keys(REVIEW_DATA.pages);
    state.selectedPage = k[0];
    if (state.selectedPage) renderPageView(state.selectedPage);
  }
  renderSidebar();
}

// ── Field view ──
function renderFieldView(field) {
  const content = document.getElementById('content');
  const change = state.schemaChanges[field.name];
  const isDropped = change?.action === 'drop';
  const isKept = change?.action === 'keep';
  const isDiscovered = field.source === 'discovered';
  const desc = state.descriptions[field.name] || '';
  const pks = Object.keys(REVIEW_DATA.pages);

  const displayName = change?.action === 'rename' ? change.newName : field.name;

  let fieldActions;
  if (isDropped) {
    fieldActions = `<button class="schema-ctrl-btn" onclick="restoreField('${field.name}')">Restore</button>`;
  } else if (isDiscovered && !isKept) {
    fieldActions = `<button class="schema-ctrl-btn ok" onclick="keepField('${field.name}')">Keep</button><button class="schema-ctrl-btn danger" onclick="dropField('${field.name}')">Drop</button>`;
  } else if (isDiscovered && isKept) {
    fieldActions = `<span class="kept-badge">Kept</span><button class="schema-ctrl-btn danger" onclick="dropField('${field.name}')">Drop</button>`;
  } else {
    fieldActions = `<button class="schema-ctrl-btn danger" onclick="dropField('${field.name}')">Drop</button>`;
  }

  let h = `<div class="field-header">
    <div class="field-name-row">
      <span class="field-name" data-field="${field.name}">${displayName}</span>
      <span class="source-badge ${field.source}">${field.source}</span>
      <span class="field-type">${field.type}</span>
      ${fieldActions}
    </div>
    <div class="field-description" contenteditable="true" data-field="${field.name}" data-placeholder="Add description\u2026">${escapeHtml(desc)}</div>
  </div><div class="value-list">`;

  pks.forEach(pk => {
    const vd = field.values[pk];
    const ak = `${field.name}:${pk}`;
    const action = state.actions[ak];
    const hasVal = vd && vd.value !== null && vd.value !== undefined;
    const origVs = hasVal ? (typeof vd.value === 'object' ? JSON.stringify(vd.value, null, 2) : String(vd.value)) : '';
    const vs = action?.type === 'correct' ? action.correctedValue : origVs;
    const trunc = vs.length > 200;

    h += `<div class="value-row">
      <div class="vr-actions">
        <button class="approve-btn${action?.type==='approve'?' active':''}" onclick="setAction('${field.name}','${pk}','approve')">OK</button>
        <button class="edit-btn${action?.type==='correct'?' active':''}" data-action="edit" data-field="${field.name}" data-page="${pk}">Edit</button>
        <button class="flag-btn${action?.type==='flag'?' active':''}" data-action="flag" data-field="${field.name}" data-page="${pk}">Flag</button>
      </div>`;

    if (hasVal || action?.type === 'correct') {
      h += `<div class="vr-body"><div class="vr-value${trunc?' truncated':''}">${escapeHtml(vs)}</div>`;
      if (trunc) h += `<button type="button" class="vr-expand" onclick="toggleExpand(this)">Show more</button>`;
      h += `</div>`;
    } else {
      h += `<div class="vr-missing">not extracted</div>`;
    }

    h += `<div class="vr-page"><a href="#" onclick="switchToPage('${pk}');return false;" title="${REVIEW_DATA.pages[pk].url}">${pk}</a></div>
    </div>`;
  });

  h += `</div><button class="approve-all-btn" onclick="approveAllValues('${field.name}')">Approve all</button>`;
  content.innerHTML = h;
  attachPopoverHandlers(content);
}

// ── Page view ──
function renderPageView(pk) {
  const content = document.getElementById('content');
  const page = REVIEW_DATA.pages[pk];
  const pks = Object.keys(REVIEW_DATA.pages);
  const idx = pks.indexOf(pk);

  let fh = '';
  REVIEW_DATA.fields.forEach(field => {
    if (state.schemaChanges[field.name]?.action === 'drop') return;
    const vd = field.values[pk];
    const ak = `${field.name}:${pk}`;
    const action = state.actions[ak];
    const hasVal = vd && vd.value !== null && vd.value !== undefined;
    const origVs = hasVal ? (typeof vd.value === 'object' ? JSON.stringify(vd.value, null, 2) : String(vd.value)) : '';
    const vs = action?.type === 'correct' ? action.correctedValue : origVs;
    const trunc = vs.length > 150;

    fh += `<div class="value-card">
      <div class="vc-header"><span class="vc-name">${field.name}</span><span class="vc-type">${field.type}</span></div>`;

    if (hasVal || action?.type === 'correct') {
      fh += `<div class="vc-body"><div class="vc-content${trunc?' truncated':''}">${escapeHtml(vs)}</div>`;
      if (trunc) fh += `<button type="button" class="vc-expand" onclick="toggleExpand(this)">Show more</button>`;
      fh += `</div>`;
    } else {
      fh += `<div class="vc-missing">not extracted</div>`;
    }

    fh += `<div class="vc-actions">
      <button class="approve-btn${action?.type==='approve'?' active':''}" onclick="setAction('${field.name}','${pk}','approve')">OK</button>
      <button class="edit-btn${action?.type==='correct'?' active':''}" data-action="edit" data-field="${field.name}" data-page="${pk}">Edit</button>
      <button class="flag-btn${action?.type==='flag'?' active':''}" data-action="flag" data-field="${field.name}" data-page="${pk}">Flag</button>
    </div></div>`;
  });

  const prev = idx > 0 ? pks[idx-1] : null;
  const next = idx < pks.length-1 ? pks[idx+1] : null;

  fh += `<button class="approve-all-btn" onclick="approveAllValuesForPage('${pk}')">Approve all</button>`;

  content.innerHTML = `<div class="page-view-layout">
    <div class="page-view-fields">${fh}</div>
    <div class="page-view-iframe-container">
      <div class="iframe-controls">
        <span>${page.url}</span>
        <div style="display:flex;gap:6px;align-items:center;">
          <a href="${page.url}" target="_blank">Open live</a>
          <div class="page-nav">
            ${prev?`<button onclick="state.selectedPage='${prev}';renderSidebar();renderPageView('${prev}')">Prev</button>`:''}
            ${next?`<button onclick="state.selectedPage='${next}';renderSidebar();renderPageView('${next}')">Next</button>`:''}
          </div>
        </div>
      </div>
      <iframe src="pages/${pk}.html" sandbox="allow-same-origin" onload="forceIframeLightMode(this)"></iframe>
    </div></div>`;

  attachPopoverHandlers(content);
}

// ── Popover system ──
function attachPopoverHandlers(container) {
  container.querySelectorAll('[data-action="edit"]').forEach(b =>
    b.addEventListener('click', e => { e.stopPropagation(); showEditPopover(b, b.dataset.field, b.dataset.page); }));
  container.querySelectorAll('[data-action="flag"]').forEach(b =>
    b.addEventListener('click', e => { e.stopPropagation(); showFlagPopover(b, b.dataset.field, b.dataset.page); }));
  container.querySelectorAll('.field-name[data-field]').forEach(el =>
    el.addEventListener('click', e => { e.stopPropagation(); startInlineRename(el.dataset.field); }));
  container.querySelectorAll('.field-description[contenteditable]').forEach(el => {
    el.addEventListener('blur', () => {
      state.descriptions[el.dataset.field] = el.textContent.trim();
      updateFeedback();
    });
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); el.blur(); }
    });
  });
}

function closePopover() {
  document.querySelectorAll('.popover,.popover-overlay').forEach(el => el.remove());
}

function createPopover(anchor, html, onConfirm) {
  closePopover();
  const overlay = document.createElement('div');
  overlay.className = 'popover-overlay';
  overlay.addEventListener('click', closePopover);
  document.body.appendChild(overlay);

  const pop = document.createElement('div');
  pop.className = 'popover';
  pop.innerHTML = html + `<div class="popover-actions">
    <button class="popover-cancel">Cancel</button>
    <button class="popover-confirm">OK</button></div>`;
  document.body.appendChild(pop);

  const r = anchor.getBoundingClientRect();
  let top = r.bottom + 4, left = r.left;
  const pw = pop.offsetWidth, ph = pop.offsetHeight;
  if (left + pw > window.innerWidth - 8) left = window.innerWidth - pw - 8;
  if (left < 8) left = 8;
  if (top + ph > window.innerHeight - 8) top = r.top - ph - 4;
  pop.style.top = top + 'px';
  pop.style.left = left + 'px';

  pop.querySelector('.popover-cancel').addEventListener('click', closePopover);
  pop.querySelector('.popover-confirm').addEventListener('click', () => { onConfirm(pop); closePopover(); });
  return pop;
}

function showEditPopover(anchor, fieldName, pageKey) {
  const field = REVIEW_DATA.fields.find(f => f.name === fieldName);
  const cv = field?.values[pageKey]?.value ?? '';
  const origVs = typeof cv === 'object' ? JSON.stringify(cv, null, 2) : String(cv);
  const existing = state.actions[`${fieldName}:${pageKey}`];
  const editVs = existing?.type === 'correct' ? existing.correctedValue : origVs;
  const editNote = existing?.type === 'correct' ? (existing.note || '') : '';

  createPopover(anchor, `<h4>Edit: ${fieldName}</h4>
    <p>Original:</p><div class="current-value-preview">${escapeHtml(origVs)}</div>
    <p>Corrected:</p><textarea id="pop-val">${escapeHtml(editVs)}</textarea>
    <p>Note:</p><input id="pop-note" value="${escapeHtml(editNote)}" placeholder="optional">`, pop => {
    state.actions[`${fieldName}:${pageKey}`] = {
      type:'correct', correctedValue: pop.querySelector('#pop-val').value,
      note: pop.querySelector('#pop-note').value, originalValue: origVs };
    refreshCurrentView(); updateFeedback();
  });
}

function showFlagPopover(anchor, fieldName, pageKey) {
  const existing = state.actions[`${fieldName}:${pageKey}`];
  const et = existing?.flagType || '';

  const pop = createPopover(anchor, `<h4>Flag: ${fieldName}</h4>
    <div class="flag-pills">
      <div class="flag-pill${et==='wrong_value'?' selected':''}" data-value="wrong_value">Wrong value</div>
      <div class="flag-pill${et==='missing'?' selected':''}" data-value="missing">Missing but exists</div>
      <div class="flag-pill${et==='formatting'?' selected':''}" data-value="formatting">Formatting</div>
      <div class="flag-pill${et==='other'?' selected':''}" data-value="other">Other</div>
    </div>
    <textarea id="pop-flag-note" placeholder="Describe...">${existing?.note||''}</textarea>`, pop => {
    const sel = pop.querySelector('.flag-pill.selected');
    state.actions[`${fieldName}:${pageKey}`] = {
      type:'flag', flagType: sel ? sel.dataset.value : 'other',
      note: pop.querySelector('#pop-flag-note').value };
    refreshCurrentView(); updateFeedback();
  });

  pop.querySelectorAll('.flag-pill').forEach(p =>
    p.addEventListener('click', () => {
      pop.querySelectorAll('.flag-pill').forEach(x => x.classList.remove('selected'));
      p.classList.add('selected');
    }));
}

function showRenamePopover(anchor, fieldName) {
  createPopover(anchor, `<h4>Rename</h4><input id="pop-rename" value="${fieldName}">`, pop => {
    const n = pop.querySelector('#pop-rename').value.trim();
    if (n && n !== fieldName) { state.schemaChanges[fieldName] = { action:'rename', newName:n }; refreshCurrentView(); updateFeedback(); }
  });
}

function showDescriptionPopover(anchor, fieldName) {
  createPopover(anchor, `<h4>Description</h4><textarea id="pop-desc">${escapeHtml(state.descriptions[fieldName]||'')}</textarea>`, pop => {
    state.descriptions[fieldName] = pop.querySelector('#pop-desc').value;
    refreshCurrentView(); updateFeedback();
  });
}

// ── Inline rename ──
function startInlineRename(fieldName) {
  const nameEl = document.querySelector(`.field-name[data-field="${fieldName}"]`);
  if (!nameEl) return;
  const currentName = state.schemaChanges[fieldName]?.action === 'rename'
    ? state.schemaChanges[fieldName].newName : fieldName;
  const input = document.createElement('input');
  input.type = 'text';
  input.value = currentName;
  input.className = 'inline-rename-input';
  nameEl.replaceWith(input);
  input.focus();
  input.select();
  const save = () => {
    const n = input.value.trim();
    if (n && n !== fieldName) state.schemaChanges[fieldName] = { action:'rename', newName:n };
    else if (state.schemaChanges[fieldName]?.action === 'rename') delete state.schemaChanges[fieldName];
    refreshCurrentView();
    updateFeedback();
  };
  input.addEventListener('blur', save);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
    if (e.key === 'Escape') { refreshCurrentView(); }
  });
}

// ── Actions ──
function setAction(fn, pk, type) {
  const k = `${fn}:${pk}`;
  if (state.actions[k]?.type === type) delete state.actions[k];
  else state.actions[k] = { type };
  refreshCurrentView(); updateFeedback();
}

function approveAllValues(fn) {
  Object.keys(REVIEW_DATA.pages).forEach(pk => { state.actions[`${fn}:${pk}`] = { type:'approve' }; });
  refreshCurrentView(); updateFeedback();
}

function approveAllValuesForPage(pk) {
  REVIEW_DATA.fields.forEach(f => {
    if (state.schemaChanges[f.name]?.action !== 'drop') state.actions[`${f.name}:${pk}`] = { type:'approve' };
  });
  refreshCurrentView(); updateFeedback();
}

function keepField(fn) { state.schemaChanges[fn] = { action:'keep' }; refreshCurrentView(); updateFeedback(); }
function dropField(fn) { state.schemaChanges[fn] = { action:'drop' }; refreshCurrentView(); updateFeedback(); }
function restoreField(fn) { delete state.schemaChanges[fn]; refreshCurrentView(); updateFeedback(); }

function switchToPage(pk) {
  state.currentView = 'page';
  state.selectedPage = pk;
  document.querySelectorAll('#view-toggle button').forEach(b => {
    b.classList.toggle('active', b.dataset.view === 'page');
  });
  renderSidebar();
  renderPageView(pk);
  pushState();
}

// ── History ──
function pushState() {
  const s = { view: state.currentView, field: state.selectedField, page: state.selectedPage };
  history.pushState(s, '');
}

function setupHistory() {
  // Replace initial state
  history.replaceState({ view: state.currentView, field: state.selectedField, page: state.selectedPage }, '');

  window.addEventListener('popstate', (e) => {
    if (!e.state) return;
    state.currentView = e.state.view;
    state.selectedField = e.state.field;
    state.selectedPage = e.state.page;

    document.querySelectorAll('#view-toggle button').forEach(b => {
      b.classList.toggle('active', b.dataset.view === state.currentView);
    });

    if (state.currentView === 'field' && state.selectedField) {
      const f = REVIEW_DATA.fields.find(x => x.name === state.selectedField);
      if (f) renderFieldView(f);
    } else if (state.currentView === 'page' && state.selectedPage) {
      renderPageView(state.selectedPage);
    }
    renderSidebar();
  });
}

// ── Feedback ──
function generateFeedbackText() {
  let t = '';
  let sl = [];
  REVIEW_DATA.fields.forEach(f => {
    const c = state.schemaChanges[f.name];
    const d = state.descriptions[f.name];
    const od = f.description || '';
    if (c?.action === 'drop') sl.push(`  ${f.name}: dropped`);
    else if (c?.action === 'keep') { let l = `  ${f.name} (${f.type}): "${d}" [kept]`; sl.push(l); }
    else if (c?.action === 'rename') sl.push(`  ${f.name} -> ${c.newName} (${f.type}): "${d}"`);
    else { let l = `  ${f.name} (${f.type}): "${d}"`; if (d !== od) l += ' [updated]'; sl.push(l); }
  });
  if (sl.length) t += 'Schema:\n' + sl.join('\n') + '\n\n';

  let vl = [];
  Object.entries(state.actions).forEach(([k, a]) => {
    const [fn, ...pp] = k.split(':');
    const pk = pp.join(':');
    if (a.type === 'correct') {
      let l = `  ${fn}, ${pk}: corrected "${a.originalValue}" -> "${a.correctedValue}"`;
      if (a.note) l += ` (${a.note})`;
      vl.push(l);
    } else if (a.type === 'flag') {
      vl.push(`  ${fn}${pk?`, ${pk}`:''}: ${a.flagType} — ${a.note}`);
    }
  });

  REVIEW_DATA.fields.forEach(f => {
    const pks = Object.keys(REVIEW_DATA.pages);
    const ap = pks.filter(pk => state.actions[`${f.name}:${pk}`]?.type === 'approve');
    if (ap.length === pks.length) vl.push(`  ${f.name}: approved (all pages)`);
    else if (ap.length) vl.push(`  ${f.name}: approved (${ap.join(', ')})`);
  });

  if (vl.length) t += 'Values:\n' + vl.join('\n') + '\n';
  return t;
}

function updateFeedback() {
  const list = document.getElementById('feedback-list');
  const textarea = document.getElementById('feedback-text');
  const badge = document.getElementById('feedback-count-badge');

  const items = [];
  Object.entries(state.schemaChanges).forEach(([fn, c]) => {
    if (c.action === 'keep') items.push({ key:`schema:${fn}`, text:`${fn}: kept` });
    else if (c.action === 'drop') items.push({ key:`schema:${fn}`, text:`${fn}: dropped` });
    else if (c.action === 'rename') items.push({ key:`schema:${fn}`, text:`${fn} → ${c.newName}` });
  });
  Object.entries(state.actions).forEach(([k, a]) => {
    const [fn, ...pp] = k.split(':');
    const pk = pp.join(':');
    if (a.type === 'correct') items.push({ key:k, text:`${fn} (${pk}): edited` });
    else if (a.type === 'flag') items.push({ key:k, text:`${fn}${pk?` (${pk})`:''}: ${a.flagType}` });
  });

  list.innerHTML = items.map(i => `<div class="feedback-item">
    <span>${escapeHtml(i.text)}</span>
    <span class="remove-feedback" onclick="removeAction('${i.key}')">&times;</span></div>`).join('');

  textarea.value = generateFeedbackText();

  const approveCount = Object.values(state.actions).filter(a => a.type === 'approve').length;
  const cnt = items.length + approveCount;
  badge.textContent = cnt > 0 ? ` (${cnt})` : '';
  updateActionButtons();
}

function removeAction(k) {
  if (k.startsWith('schema:')) delete state.schemaChanges[k.slice(7)];
  else delete state.actions[k];
  refreshCurrentView(); updateFeedback();
}

// ── Helpers ──
function refreshCurrentView() {
  const el = document.getElementById('content');
  const st = el.scrollTop;
  if (state.currentView === 'field' && state.selectedField) {
    const f = REVIEW_DATA.fields.find(x => x.name === state.selectedField);
    if (f) renderFieldView(f);
  } else if (state.currentView === 'page' && state.selectedPage) {
    renderPageView(state.selectedPage);
  }
  renderSidebar();
  el.scrollTop = st;
}

function getFieldStatus(fn) {
  const pks = Object.keys(REVIEW_DATA.pages);
  const acts = pks.map(pk => state.actions[`${fn}:${pk}`]?.type).filter(Boolean);
  if (state.schemaChanges[fn]?.action === 'drop') return 'dropped';
  if (acts.some(a => a==='flag')) return 'flagged';
  if (acts.some(a => a==='correct')) return 'corrected';
  if (acts.length === pks.length && acts.every(a => a==='approve')) return 'approved';
  return 'unreviewed';
}

function getPageStatus(pk) {
  const fs = REVIEW_DATA.fields.filter(f => state.schemaChanges[f.name]?.action !== 'drop');
  const acts = fs.map(f => state.actions[`${f.name}:${pk}`]?.type).filter(Boolean);
  if (acts.some(a => a==='flag')) return 'flagged';
  if (acts.some(a => a==='correct')) return 'corrected';
  if (acts.length === fs.length && acts.every(a => a==='approve')) return 'approved';
  return 'unreviewed';
}

function toggleExpand(el) {
  const v = el.previousElementSibling;
  v.classList.toggle('truncated');
  v.classList.toggle('expanded');
  el.textContent = v.classList.contains('expanded') ? 'Show less' : 'Show more';
}

function makeReadOnly() {
  clearStatusNotice();
  document.body.classList.add('read-only');
  const banner = document.createElement('div');
  banner.id = 'readonly-banner';
  banner.textContent = 'Feedback sent. The agent will open an updated review if needed.';
  document.body.insertBefore(banner, document.body.firstChild);
  // Hide header controls except theme and the clicked button
  document.getElementById('header-copy').style.display = 'none';
  document.getElementById('feedback-trigger').style.display = 'none';
  const approve = document.getElementById('header-approve');
  const changes = document.getElementById('header-request-changes');
  if (!approve.classList.contains('sent')) approve.style.display = 'none';
  if (!changes.classList.contains('sent')) changes.style.display = 'none';
}

function getStatusNotice() {
  let notice = document.getElementById('status-notice');
  if (notice) return notice;

  notice = document.createElement('div');
  notice.id = 'status-notice';
  notice.className = 'hidden';
  notice.setAttribute('role', 'alert');
  notice.setAttribute('aria-live', 'assertive');
  notice.innerHTML = `<div class="status-notice__body"></div><button type="button" class="status-notice__close" aria-label="Dismiss notification">&times;</button>`;
  notice.querySelector('.status-notice__close').addEventListener('click', clearStatusNotice);
  document.body.appendChild(notice);
  return notice;
}

function showStatusNotice(message) {
  const notice = getStatusNotice();
  notice.querySelector('.status-notice__body').textContent = message;
  notice.classList.remove('hidden');
}

function clearStatusNotice() {
  const notice = document.getElementById('status-notice');
  if (!notice) return;
  notice.classList.add('hidden');
}

function escapeHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
