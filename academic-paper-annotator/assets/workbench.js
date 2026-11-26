/* Static reader controls; content remains readable without this script. */
'use strict';
(() => {
  const all = selector => [...document.querySelectorAll(selector)];
  const one = selector => document.querySelector(selector);
  const units = all('.unit');
  const entries = all('[data-search]');
  const body = document.body;
  let hits = [], hitIndex = -1, onlyDeep = false, searchState = null;
  let printState = null, ticking = false;

  function applyFilter() {
    units.forEach(unit => unit.classList.toggle('hidden', onlyDeep && unit.dataset.depth !== 'deep'));
  }
  function reveal(element) {
    element.classList.remove('hidden');
    for (let parent = element; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    if (element.matches('.unit')) {
      const annotation = element.querySelector('details');
      if (annotation) annotation.open = true;
    }
  }
  function revealSearchResult(element) {
    // A match must be visible even when it belongs to a hidden translation/annotation.
    body.dataset.mode = 'bilingual';
    one('#mode').value = 'bilingual';
    body.classList.remove('no-annotations');
    one('#annotations').checked = true;
    reveal(element);
  }
  function jump(delta) {
    if (!hits.length) return;
    hits.forEach(element => element.classList.remove('search-hit'));
    hitIndex = (hitIndex + delta + hits.length) % hits.length;
    const element = hits[hitIndex];
    revealSearchResult(element);
    element.classList.add('search-hit');
    element.scrollIntoView({block: 'center'});
    one('#results').textContent = `${hitIndex + 1} / ${hits.length} 个匹配单元`;
  }
  function search() {
    all('.search-hit').forEach(element => element.classList.remove('search-hit'));
    const term = one('#search').value.trim().toLocaleLowerCase();
    if (!term) { clearSearch(); return; }
    if (!searchState) searchState = {mode: body.dataset.mode || 'bilingual', annotations: !body.classList.contains('no-annotations')};
    hits = entries.filter(element => element.textContent.toLocaleLowerCase().includes(term));
    hitIndex = -1;
    one('#results').textContent = `${hits.length} 个匹配单元`;
    if (hits.length) jump(1);
  }
  function clearSearch() {
    one('#search').value = '';
    hits = []; hitIndex = -1;
    all('.search-hit').forEach(element => element.classList.remove('search-hit'));
    if (searchState) {
      body.dataset.mode = searchState.mode;
      one('#mode').value = searchState.mode;
      body.classList.toggle('no-annotations', !searchState.annotations);
      one('#annotations').checked = searchState.annotations;
      searchState = null;
    }
    applyFilter();
    one('#results').textContent = '搜索已清除';
    one('#search').focus();
  }
  function beforePrint() {
    // Some browsers emit beforeprint more than once for the same preview.
    if (printState !== null) return;
    printState = all('details').map(element => [element, element.open]);
    printState.forEach(([element]) => { element.open = true; });
  }
  function afterPrint() {
    if (printState === null) return;
    printState.forEach(([element, open]) => { element.open = open; });
    printState = null;
  }
  function progress() {
    const total = document.documentElement.scrollHeight - innerHeight;
    const value = total > 0 ? Math.max(0, Math.min(100, scrollY / total * 100)) : 0;
    one('#progress').value = value;
    one('#progress-text').textContent = `浏览 ${Math.round(value)}%`;
    const visible = units.filter(element => !element.classList.contains('hidden') && element.getBoundingClientRect().top <= 220);
    const active = visible[visible.length - 1];
    if (active) {
      all('.reading-current').forEach(element => element.classList.remove('reading-current'));
      active.classList.add('reading-current');
      one('#current').textContent = active.id + ' · ' + active.dataset.section;
    }
    ticking = false;
  }

  one('#deep').addEventListener('change', event => { onlyDeep = event.target.checked; applyFilter(); });
  one('#mode').addEventListener('change', event => {
    body.dataset.mode = event.target.value;
    if (searchState) searchState.mode = event.target.value;
  });
  one('#annotations').addEventListener('change', event => {
    body.classList.toggle('no-annotations', !event.target.checked);
    if (searchState) searchState.annotations = event.target.checked;
  });
  all('[data-hl]').forEach(control => control.addEventListener('change', () => {
    if (!['claim', 'concept', 'evidence', 'limitation', 'method'].includes(control.dataset.hl)) return;
    all('.hl.' + control.dataset.hl).forEach(mark => mark.classList.toggle('off', !control.checked));
  }));
  one('#expand').onclick = () => all('.annotation').forEach(element => { element.open = true; });
  one('#collapse').onclick = () => all('.annotation').forEach(element => { element.open = false; });
  one('#search-go').onclick = search;
  one('#search').onkeydown = event => { if (event.key === 'Enter') { event.preventDefault(); search(); } };
  one('#prev').onclick = () => jump(-1);
  one('#next').onclick = () => jump(1);
  one('#clear').onclick = clearSearch;
  all('a[href^="#"]').forEach(link => link.addEventListener('click', () => {
    let target = link.getAttribute('href').slice(1);
    try { target = decodeURIComponent(target); } catch (_) { /* Keep literal malformed fragments. */ }
    const element = document.getElementById(target);
    if (element) reveal(element);
  }));
  window.addEventListener('beforeprint', beforePrint);
  window.addEventListener('afterprint', afterPrint);
  one('#print').onclick = () => window.print();
  addEventListener('scroll', () => {
    if (!ticking) { ticking = true; requestAnimationFrame(progress); }
  }, {passive: true});
  body.classList.add('js');
  one('#controls').hidden = false;
  progress();
})();
