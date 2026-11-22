/* MYSTIQ shared front-end helpers */
const MQ = (() => {
  const csrf = document.querySelector('meta[name=csrf]')?.content || '';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function api(url, body) {
    try {
      const r = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf}, body: JSON.stringify(body || {})});
      const j = await r.json().catch(() => ({error: 'The server sent an unreadable response.'}));
      if (!r.ok && !j.error) j.error = 'Request failed (' + r.status + ')';
      j._status = r.status; return j;
    } catch (e) { return {error: 'Network problem — please try again.'}; }
  }
  async function get(url) { try { const r = await fetch(url, {headers: {'X-CSRFToken': csrf}}); return await r.json(); } catch (e) { return {error: 'Network problem.'}; } }
  const ico = n => `<svg class="ic" aria-hidden="true"><use href="#i-${n}"/></svg>`;
  const stanceIcon = st => ({direct_observation: 'eye', hearsay: 'ear', assumption: 'thought', absence_of_observation: 'void', denial: 'denial'}[st] || 'thought');
  function cited(text, cites, caseNo) {
    const map = {}; (cites || []).forEach(c => map[c.id] = c);
    return esc(text).replace(/\[E(\d+)\]/g, (m, n) => {
      const c = map['E' + n]; if (!c) return '';
      const href = c.doc_key ? `/case/${caseNo}/evidence/${c.doc_key}/` : '#';
      return `<a class="cite" href="${href}" title="${esc(c.title)}">E${n}</a>`;
    });
  }
  function sources(cites, caseNo) {
    if (!cites || !cites.length) return '';
    return '<div class="lbl" style="margin-top:8px">Sources · relevance</div>' + cites.map(c =>
      `<div class="src"><b>E${c.id.slice(1)}</b> ${c.doc_key ? `<a href="/case/${caseNo}/evidence/${c.doc_key}/">${esc(c.title)}</a>` : esc(c.title)} <span class="badge">${c.score}</span><br><span class="muted">${esc(c.snippet)}${c.snippet.length >= 240 ? '…' : ''}</span></div>`).join('');
  }
  function addMsg(box, who, html, cls) {
    const d = document.createElement('div'); d.className = 'msg ' + cls;
    d.innerHTML = `<div class="who">${esc(who)}</div><div class="body">${html}</div>`;
    box.appendChild(d); box.scrollTop = box.scrollHeight; return d;
  }
  function verdict(c) {
    const lbl = {contradiction: 'Contradiction', entailment: 'Consistent', neutral: 'Not a contradiction'}[c.label];
    const pct = Math.round(Math.min(1, Math.max(0, +c.confidence || 0)) * 100);
    return `<div class="verdict ${c.label}"><div class="vh">${ico('nli')}<span class="vt">${lbl}</span> <span class="badge">${c.finding.replace(/_/g, ' ')}</span> <span class="meter" title="confidence ${c.confidence}"><i style="width:${pct}%"></i></span><span class="small muted mono">${c.confidence}</span></div>
      ${c.title ? `<div class="small" style="margin-top:6px">vs. <a href="/case/${window.CASE_NO}/evidence/${c.doc_key}/">${esc(c.title)}</a> (${esc(c.doc_type)})</div>` : ''}
      ${c.premise ? `<div class="small muted" style="margin-top:4px">“${esc(c.premise)}”</div>` : ''}${(c.rationale || []).map(r => `<div style="margin-top:4px">${esc(r)}</div>`).join('')}</div>`;
  }
  function renderExplain(r) {
    if (r.error) return `<div class="nlp">${esc(r.error)}</div>`;
    let h = `<div class="nlp" data-ins="nli"><div class="nh">${ico('nli')}Contradiction scales · NLI ${esc(r.nli_backend)} · ${r.latency_ms} ms</div>${esc(r.summary)}</div>`;
    h += `<div class="nlp" data-ins="stance"><div class="nh">${ico('stance')}Witness lens</div><span class="stance ${r.stance.stance}">${ico(stanceIcon(r.stance.stance))}${r.stance.stance.replace(/_/g, ' ')}</span></div>`;
    if (r.times && r.times.length) h += `<div class="nlp" data-ins="time"><div class="nh">${ico('time')}Chronometer</div><span class="small">${r.times.map(t => esc(t.text) + ' → <b class="mono">' + t.label + '</b>' + (t.ambiguous ? ' (AM/PM inferred)' : '') + (t.precision !== 'exact' ? ' (' + t.precision + ')' : '')).join('; ')}</span></div>`;
    if (r.leakage && r.leakage.leaks.length) h += `<div class="nlp" data-ins="leakage"><div class="nh">${ico('leakage')}Keyhole · details found only in a private source</div><b>${r.leakage.leaks.map(l => esc(l.phrase)).join(', ')}</b> <span class="small muted">(${esc(r.leakage.leaks[0].source_title)})</span></div>`;
    return h + (r.comparisons || []).map(verdict).join('');
  }
  function tabs(root) {
    const btns = root.querySelectorAll('[role=tab]'), panels = root.querySelectorAll('.tabpanel');
    function show(id) {
      btns.forEach(b => b.setAttribute('aria-selected', b.dataset.tab === id));
      panels.forEach(p => p.classList.toggle('active', p.id === id));
      history.replaceState(null, '', '#tab-' + id);
    }
    btns.forEach(b => b.addEventListener('click', () => show(b.dataset.tab)));
    const want = (location.hash || '').replace(/^#(tab-)?/, ''); show(want && document.getElementById(want) ? want : btns[0].dataset.tab);
    return show;
  }
  return {ico, stanceIcon, api, get, esc, cited, sources, addMsg, verdict, renderExplain, tabs};
})();
