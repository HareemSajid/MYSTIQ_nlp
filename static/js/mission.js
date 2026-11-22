/* Mission tracker: shows a player where they are and what to do next. Progress is a per-browser convenience (localStorage). */
(() => {
  const N = window.CASE_NO, UID = (document.body.dataset.uid || 'u');
  const KEY = `mq:${UID}:${N}`;
  const load = () => { try { return Object.assign({tabs: [], docs: []}, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) { return {tabs: [], docs: []}; } };
  const save = s => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {} };
  let st = load();
  const add = (arr, v) => { if (!st[arr].includes(v)) { st[arr].push(v); save(st); } };
  if (window.DOC_KEY) add('docs', window.DOC_KEY);
  const STEPS = ['overview', 'suspects', 'evidence', 'statements', 'timeline', 'interrogation'];
  const NEED_DOCS = Math.min(3, +(document.body.dataset.docs || 3));
  const done = s => s === 'evidence' ? st.docs.length >= NEED_DOCS : st.tabs.includes(s);
  const MSG = {overview: 'Read the case board — know the story and your objective', suspects: 'Meet the suspects — check motives and whereabouts',
    evidence: 'Open at least ' + NEED_DOCS + ' documents', statements: 'Check the statements — who saw it, who assumed it?',
    timeline: 'Study the timeline — what do the records say?', interrogation: 'Question a suspect with something you found'};
  function render() {
    const m = document.getElementById('mission'); if (m) {
      const d = STEPS.filter(done).length, next = STEPS.find(s => !done(s));
      m.querySelectorAll('.msteps li').forEach(li => { const s = li.dataset.step; li.classList.toggle('done', done(s)); li.classList.toggle('now', s === next);
        if (s === 'evidence') li.querySelector('small').textContent = Math.min(st.docs.length, NEED_DOCS) + '/' + NEED_DOCS + ' documents'; });
      document.getElementById('mnext').textContent = next ? 'Next: ' + MSG[next] : 'You are ready — make your Final Deduction';
      const pct = Math.round(d / STEPS.length * 100);
      document.getElementById('xpfill').style.width = pct + '%'; document.getElementById('xptxt').textContent = pct + '%';
      const fd = document.getElementById('finalbtn'); if (fd) fd.classList.toggle('glow', !next);
    }
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('visited', st.tabs.includes(t.dataset.tab)));
    document.querySelectorAll('.doc-row[data-dockey]').forEach(r => r.classList.toggle('read', st.docs.includes(r.dataset.dockey)));
  }
  document.addEventListener('click', e => {
    const tab = e.target.closest('.tab'); if (tab) { add('tabs', tab.dataset.tab); render(); }
    const li = e.target.closest('.msteps li'); if (li) { const t = document.querySelector(`.tab[data-tab="${li.dataset.step}"]`); if (t) t.click(); window.scrollTo({top: 0, behavior: 'smooth'}); }
    if (e.target.closest('[data-interrogate]')) { add('tabs', 'interrogation'); render(); }
    if (e.target.id === 'tipclose') { try { localStorage.setItem('mq:tip', '1'); } catch (x) {} document.getElementById('tip').remove(); }
  });
  setTimeout(() => { const a = document.querySelector('.tab[aria-selected="true"]'); if (a) add('tabs', a.dataset.tab); render(); }, 250);
  try { if (localStorage.getItem('mq:tip') === '1') { const t = document.getElementById('tip'); if (t) t.remove(); } } catch (e) {}
  render();
  // previous / next document navigation on the evidence viewer
  const list = document.getElementById('doclist');
  if (list && window.DOC_KEY) {
    const items = [...list.querySelectorAll('li')]; const i = items.findIndex(x => x.dataset.key === window.DOC_KEY);
    const mk = (it, label, cls) => it ? `<a class="btn ghost small" href="${it.dataset.url}">${label}</a>` : '<span></span>';
    const nav = document.getElementById('docnav'); if (nav) nav.innerHTML = mk(items[i - 1], '← Previous: ' + (items[i - 1] ? items[i - 1].textContent : '')) + `<span class="lbl" style="align-self:center">Document ${i + 1} of ${items.length}</span>` + mk(items[i + 1], 'Next: ' + (items[i + 1] ? items[i + 1].textContent : '') + ' →');
  }
})();
