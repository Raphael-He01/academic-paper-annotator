'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../academic-paper-annotator/assets/workbench.js'), 'utf8');

function fixture() {
  class Classes {
    constructor() { this.values = new Set(); }
    add(...x) { x.forEach(v => this.values.add(v)); }
    remove(...x) { x.forEach(v => this.values.delete(v)); }
    contains(x) { return this.values.has(x); }
    toggle(x, on = !this.contains(x)) { on ? this.add(x) : this.remove(x); return on; }
  }
  const callbacks = {};
  const element = () => ({classList: new Classes(), dataset: {}, hidden: false, value: '', checked: true, textContent: '', events: {}, addEventListener(n, fn) { this.events[n] = fn; }, focus() {}});
  const controls = {};
  for (const id of ['controls', 'deep', 'mode', 'annotations', 'expand', 'collapse', 'search', 'search-go', 'prev', 'next', 'clear', 'results', 'print', 'progress', 'progress-text', 'current']) controls['#' + id] = element();
  const body = {...element(), tagName: 'BODY'};
  const details = [false, true].map(open => ({...element(), open, tagName: 'DETAILS'}));
  const units = details.map((detail, i) => ({...element(), id: 'P00' + (i + 1), dataset: {depth: i ? 'deep' : 'brief', section: 'Demo'}, textContent: 'English 中文译文 AnnotationUniqueTerm ' + i, parentElement: body, matches: s => s === '.unit', querySelector: () => detail, getBoundingClientRect: () => ({top: 0}), scrollIntoView() {}}));
  details.forEach((d, i) => { d.parentElement = units[i]; });
  const marks = [element()];
  const toggle = element(); toggle.dataset.hl = 'evidence';
  const document = {body, documentElement: {scrollHeight: 2000}, querySelector: s => controls[s], getElementById: id => units.find(u => u.id === id), querySelectorAll(s) {
    if (s === '.unit' || s === '[data-search]') return units;
    if (s === '.annotation' || s === 'details') return details;
    if (s === '[data-hl]') return [toggle];
    if (s === '.hl.evidence') return marks;
    if (s === '.search-hit' || s === '.reading-current') return units.filter(u => u.classList.contains(s.slice(1)));
    return [];
  }};
  const window = {addEventListener: (name, fn) => { callbacks[name] = fn; }, print() {}};
  const context = {document, window, innerHeight: 1000, scrollY: 0, requestAnimationFrame: fn => fn(), addEventListener: window.addEventListener};
  vm.runInNewContext(source, context);
  return {body, controls, details, units, marks, toggle, callbacks};
}

test('search exposes hidden annotations and restores preference on clear', () => {
  const f = fixture();
  f.controls['#annotations'].events.change({target: {checked: false}});
  f.controls['#search'].value = 'AnnotationUniqueTerm'; f.controls['#search-go'].onclick();
  assert.equal(f.body.classList.contains('no-annotations'), false);
  assert.equal(f.details[0].open, true);
  f.controls['#clear'].onclick();
  assert.equal(f.body.classList.contains('no-annotations'), true);
});
test('Chinese match is exposed in English-only mode and previous mode restored', () => {
  const f = fixture();
  f.controls['#mode'].events.change({target: {value: 'english'}});
  f.controls['#search'].value = '中文'; f.controls['#search-go'].onclick();
  assert.equal(f.body.dataset.mode, 'bilingual');
  f.controls['#clear'].onclick(); assert.equal(f.body.dataset.mode, 'english');
});
test('repeated beforeprint preserves original states', () => {
  const f = fixture();
  f.callbacks.beforeprint(); f.callbacks.beforeprint();
  assert(f.details.every(d => d.open));
  f.callbacks.afterprint(); f.callbacks.afterprint();
  assert.deepEqual(f.details.map(d => d.open), [false, true]);
});
test('search can reveal a brief hit then clearing restores deep filter', () => {
  const f = fixture(); f.controls['#deep'].events.change({target: {checked: true}});
  assert(f.units[0].classList.contains('hidden'));
  f.controls['#search'].value = 'AnnotationUniqueTerm'; f.controls['#search-go'].onclick();
  assert(!f.units[0].classList.contains('hidden'));
  f.controls['#next'].onclick(); assert(f.controls['#results'].textContent.startsWith('2 / 2'));
  f.controls['#prev'].onclick(); f.controls['#clear'].onclick();
  assert(f.units[0].classList.contains('hidden'));
});
test('highlight toggle changes styling without removing content', () => {
  const f = fixture(); f.toggle.checked = false; f.toggle.events.change();
  assert(f.marks[0].classList.contains('off'));
  f.toggle.checked = true; f.toggle.events.change(); assert(!f.marks[0].classList.contains('off'));
});
