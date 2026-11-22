(() => {
  const N = window.CASE_NO, $ = s => document.querySelector(s), $$ = s => document.querySelectorAll(s);
  const show = MQ.tabs($('#tabs').parentElement);
  // clock
  const clk = $('#clock'); let secs = +clk.dataset.start;
  setInterval(() => { secs++; clk.textContent = Math.floor(secs / 60) + ':' + String(secs % 60).padStart(2, '0'); }, 1000);
  // notebook autosave
  let nbT; $('#notebook').addEventListener('input', e => { $('#nbstatus').textContent = 'Saving…'; clearTimeout(nbT);
    nbT = setTimeout(async () => { const r = await MQ.api(`/api/case/${N}/notebook/`, {text: e.target.value}); $('#nbstatus').textContent = r.saved ? 'Saved to your casebook.' : 'Could not save.'; }, 700); });
  // important stars
  $$('[data-star]').forEach(b => b.addEventListener('click', async () => { const r = await MQ.api(`/api/case/${N}/important/`, {doc_key: b.dataset.star}); if (!r.error) b.classList.toggle('on', r.important); }));
  // ask the case files
  const askchat = $('#askchat');
  async function ask() {
    const q = $('#askq').value.trim(); if (q.length < 3) return; $('#askq').value = '';
    MQ.addMsg(askchat, 'You', MQ.esc(q), 'me'); const w = MQ.addMsg(askchat, 'MYSTIQ', '<span class="spinner"></span>', 'them');
    $('#askbtn').disabled = true; const r = await MQ.api(`/api/case/${N}/ask/`, {question: q}); $('#askbtn').disabled = false;
    if (r.error) { w.querySelector('.body').innerHTML = MQ.esc(r.error); return; }
    let h = MQ.cited(r.answer, r.citations, N) + MQ.sources(r.citations, N);
    h += `<div class="nlp small muted">${r.insufficient ? 'Insufficient evidence. ' : ''}retrieval: ${r.retrieval.backend} · ${r.retrieval.latency_ms} ms${r.retrieval.cached ? ' (cached)' : ''} · intent: ${r.retrieval.intents.join(', ')} · generator: ${r.mode}${r.fallback_reason ? ' (fallback: ' + MQ.esc(r.fallback_reason) + ')' : ''}</div>`;
    if (r.analysis) h += MQ.renderExplain(r.analysis);
    w.querySelector('.body').innerHTML = h; askchat.scrollTop = askchat.scrollHeight;
  }
  $('#askbtn').addEventListener('click', ask); $('#askq').addEventListener('keydown', e => { if (e.key === 'Enter') ask(); });
  // statements: explain + compare
  $$('[data-explain]').forEach(b => b.addEventListener('click', async () => {
    const out = $('#ex-' + b.dataset.explain); out.innerHTML = '<span class="spinner"></span> Comparing with the case files…'; b.disabled = true;
    out.innerHTML = MQ.renderExplain(await MQ.api(`/api/case/${N}/explain/`, {statement_id: +b.dataset.explain})); b.disabled = false; }));
  $('#cmpbtn').addEventListener('click', async () => {
    const out = $('#cmpout'); out.innerHTML = '<span class="spinner"></span>';
    const r = await MQ.api(`/api/case/${N}/compare/`, {a: +$('#cmpa').value, b: +$('#cmpb').value});
    out.innerHTML = r.error ? `<div class="nlp">${MQ.esc(r.error)}</div>` : `<div class="nlp">${MQ.verdict(r)}<div class="small muted">backend: ${MQ.esc(r.backend)} · ${r.latency_ms} ms · same people: ${r.comparable.same_people} · same day: ${r.comparable.same_day} · same place: ${r.comparable.same_place}</div></div>`; });
  // interrogation (portrait picker)
  let cur = $('#pick .pickbtn').dataset.pick, curName = $('#pick .pickbtn').dataset.name;
  function swap() { $$('.ichat').forEach(c => c.style.display = c.id === 'ic-' + cur ? '' : 'none'); $$('.pickbtn').forEach(b => b.setAttribute('aria-pressed', b.dataset.pick === cur)); }
  $$('.pickbtn').forEach(b => b.addEventListener('click', () => { cur = b.dataset.pick; curName = b.dataset.name; swap(); $('#iq').focus(); }));
  $$('[data-interrogate]').forEach(b => b.addEventListener('click', () => { const p = document.querySelector(`.pickbtn[data-pick="${b.dataset.interrogate}"]`); cur = p.dataset.pick; curName = p.dataset.name; swap(); show('interrogation'); $('#iq').focus(); }));
  async function interrogate() {
    const q = $('#iq').value.trim(); if (q.length < 3) return; $('#iq').value = ''; const key = cur, box = $('#ic-' + key), name = curName;
    MQ.addMsg(box, 'You', MQ.esc(q), 'me'); const w = MQ.addMsg(box, name, '', 'them loading'); $('#ibtn').disabled = true;
    const r = await MQ.api(`/api/case/${N}/interrogate/`, {suspect: key, question: q, present: $('#ipres').value}); $('#ibtn').disabled = false; w.classList.remove('loading');
    w.querySelector('.body').innerHTML = MQ.esc(r.error || r.answer) + (r.error ? '' : `<div class="small muted mono">${r.latency_ms} ms · ${r.mode}</div>`); }
  $('#ibtn').addEventListener('click', interrogate); $('#iq').addEventListener('keydown', e => { if (e.key === 'Enter') interrogate(); });
  // Watson
  const wchat = $('#wchat'); wchat.scrollTop = wchat.scrollHeight;
  async function watson() {
    const q = $('#wq').value.trim(); if (q.length < 3) return; $('#wq').value = '';
    MQ.addMsg(wchat, 'You', MQ.esc(q), 'me'); const w = MQ.addMsg(wchat, 'Dr. Watson', '<span class="spinner"></span>', 'them'); $('#wbtn').disabled = true;
    const r = await MQ.api(`/api/case/${N}/watson/`, {question: q}); $('#wbtn').disabled = false;
    w.querySelector('.body').innerHTML = r.error ? MQ.esc(r.error) : MQ.cited(r.answer, r.citations, N) + MQ.sources(r.citations, N); }
  $('#wbtn').addEventListener('click', watson); $('#wq').addEventListener('keydown', e => { if (e.key === 'Enter') watson(); });
  $('#hintbtn').addEventListener('click', async () => {
    if (!confirm('Each hint costs 75 points. Call Dr. Watson for the next hint?')) return;
    const b = $('#hintbtn'); b.disabled = true; const r = await MQ.api(`/api/case/${N}/hint/`);
    if (r.error) { alert(r.message || r.error); return; }
    $('#hints').insertAdjacentHTML('beforeend', `<div class="hintcard"><b>Hint ${r.order}</b>${MQ.esc(r.text)}${r.look_at.length ? '<div class="small">Worth re-reading: ' + r.look_at.map(l => `<a href="/case/${N}/evidence/${l.doc_key}/">${MQ.esc(l.title)}</a>`).join(', ') + '</div>' : ''}</div>`);
    $('#hintcount').textContent = r.hints_used; b.textContent = `Request next hint (${r.hints_used}/${r.hints_total} used)`; b.disabled = r.hints_used >= r.hints_total; });
})();
