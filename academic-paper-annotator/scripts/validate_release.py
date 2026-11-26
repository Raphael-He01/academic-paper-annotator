#!/usr/bin/env python3
"""Audit final static content and recorded review evidence; no network or browser."""
import argparse
import base64
import binascii
import hashlib
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

CATEGORIES = {'claim', 'concept', 'evidence', 'limitation', 'method'}
VOID_TAGS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

class DataError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DataError(message)


def strings(value):
    return isinstance(value, list) and all(isinstance(x, str) and x for x in value)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_data(units, baseline, figures, tables, analysis, review):
    """Validate shapes before evaluating content; malformed data never becomes ready."""
    require(isinstance(units, list) and units, 'units must be a nonempty array')
    for i, unit in enumerate(units):
        label = f'units[{i}]'
        require(isinstance(unit, dict), label + ' must be an object')
        for key in ('id', 'unit_type', 'original_text'):
            require(isinstance(unit.get(key), str) and unit[key], f'{label}.{key} must be a nonempty string')
        for key in ('translation_zh', 'logical_role', 'critical_commentary'):
            require(isinstance(unit.get(key, ''), str), f'{label}.{key} must be a string')
        require(isinstance(unit.get('status'), dict), label + '.status must be an object')
        role = unit.get('rhetorical_function', '')
        require(isinstance(role, (str, dict)), label + '.rhetorical_function must be text or an object')
        if isinstance(role, dict):
            require(isinstance(role.get('primary'), str), label + '.rhetorical_function.primary must be text')
            require(strings(role.get('secondary', [])), label + '.rhetorical_function.secondary must be an array of text')
        for key in ('cross_references', 'citation_refs'):
            require(strings(unit.get(key, [])), f'{label}.{key} must be an array of nonempty strings')
        require(unit.get('numeric_source_text') is None or isinstance(unit['numeric_source_text'], str), label + '.numeric_source_text must be text')
        require(isinstance(unit.get('requires_translation', True), bool), label + '.requires_translation must be boolean')
        highlights = unit.get('highlights', [])
        require(isinstance(highlights, list), label + '.highlights must be an array')
        for highlight in highlights:
            require(isinstance(highlight, dict) and isinstance(highlight.get('quote'), str) and highlight['quote'], label + ': highlight requires nonempty quote')
            require(highlight.get('category') in CATEGORIES, label + ': unknown highlight category')
    require(isinstance(baseline, dict), 'baseline must be an object')
    require(strings(baseline.get('required_unit_ids')), 'baseline.required_unit_ids must be a string array')
    counts = baseline.get('unit_counts')
    require(isinstance(counts, dict) and counts and all(isinstance(k, str) and type(v) is int and v >= 0 for k, v in counts.items()), 'baseline.unit_counts must contain known nonnegative integer counts')
    for key in ('figure_count', 'table_count'):
        require(type(baseline.get(key)) is int and baseline[key] >= 0, f'baseline.{key} is unknown or invalid')
    require(strings(baseline.get('reference_ids')), 'baseline.reference_ids must be an array')
    if figures is not None:
        require(isinstance(figures, list), 'figures must be an array')
        for f in figures:
            require(isinstance(f, dict) and all(isinstance(f.get(k), str) and f[k].strip() for k in ('id', 'original_text', 'translation_zh')), 'figure requires id, original_text and translation_zh')
    if tables is not None:
        require(isinstance(tables, list), 'tables must be an array')
        for t in tables:
            require(isinstance(t, dict) and isinstance(t.get('id'), str) and t['id'], 'table requires id')
            require(isinstance(t.get('rows'), list) and t['rows'] and all(isinstance(row, list) and row and all(isinstance(c, str) for c in row) for row in t['rows']), 'table.rows must be a nonempty matrix of strings')
    if analysis is not None:
        require(isinstance(analysis, dict) and isinstance(analysis.get('claims'), list), 'analysis.claims must be an array')
        for c in analysis['claims']:
            require(isinstance(c, dict) and isinstance(c.get('id'), str) and c['id'] and isinstance(c.get('quote'), str) and c['quote'] and strings(c.get('units')) and c['units'], 'claim requires id, nonempty units and quote')
    require(isinstance(review, dict), 'review must be an object')
    for key in ('content_review', 'browser_review'):
        require(isinstance(review.get(key, {}), dict), f'review.{key} must be an object')


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids, self.links, self.resources, self.styles = [], [], [], []
        self.unit_ids = []
        self.originals, self.translations, self.annotations, self.marks = {}, {}, {}, {}
        self.text_by_id, self.figure_images, self.tables = {}, {}, {}
        self.images = []
        self.marks_in_original = True

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        ident, classes = a.get('id'), a.get('class', '').split()
        if ident:
            self.ids.append(ident)
        if 'unit' in classes:
            self.unit_ids.append(ident)
        owner = ident or next((f['id'] for f in reversed(self.stack) if f['id']), None)
        if tag == 'a' and a.get('href', '').startswith('#'):
            self.links.append(unquote(a['href'][1:]))
        if tag in ('img', 'script', 'iframe', 'object', 'embed', 'source') or (tag == 'link' and a.get('rel', '').lower() in ('stylesheet', 'preload', 'modulepreload')):
            for key in ('src', 'href', 'data', 'srcset'):
                if a.get(key):
                    self.resources.append(a[key])
        if tag == 'img':
            self.images.append(a.get('src', ''))
            self.figure_images.setdefault(owner, []).append(a.get('src', ''))
        if a.get('style'):
            self.styles.append(a['style'])
        if tag == 'mark' and not any(f['capture'] == 'original' for f in self.stack):
            self.marks_in_original = False
        table = next((f for f in reversed(self.stack) if f['tag'] == 'table'), None)
        table_key = table['table_key'] if table else None
        if tag == 'table':
            table_key = owner or f'unnamed-table-{len(self.tables)}'
            # A second source table with the same owner is kept distinct and fails matching.
            if table_key in self.tables:
                table_key += f':duplicate-{len(self.tables)}'
            self.tables[table_key] = []
        row = next((f['row'] for f in reversed(self.stack) if f['tag'] == 'tr' and f['table_key'] == table_key), None)
        if tag == 'tr' and table_key is not None:
            row = []
            self.tables[table_key].append(row)
        captures = ('original', 'translation', 'annotation', 'cell-original')
        capture = 'mark' if tag == 'mark' else next((c for c in captures if c in classes), None)
        if tag == 'style':
            capture = 'css'
        if tag in VOID_TAGS:
            return
        self.stack.append({'tag': tag, 'id': ident, 'owner': owner, 'capture': capture, 'text': '', 'table_key': table_key, 'row': row, 'category': next((c for c in classes if c in CATEGORIES), None)})

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]['tag'] != tag:
                continue
            closed, self.stack = self.stack[index:], self.stack[:index]
            for f in closed:
                kind, owner, value = f['capture'], f['owner'], f['text']
                if f['id']:
                    self.text_by_id.setdefault(f['id'], []).append(value)
                if kind in ('original', 'translation', 'annotation'):
                    target = {'original': self.originals, 'translation': self.translations, 'annotation': self.annotations}[kind]
                    target.setdefault(owner, []).append(value)
                elif kind == 'mark':
                    self.marks.setdefault(owner, []).append((value, f['category']))
                elif kind == 'cell-original' and f['row'] is not None:
                    f['row'].append(value)
                elif kind == 'css':
                    self.styles.append(value)
            return

    def handle_data(self, value):
        for frame in self.stack:
            frame['text'] += value


def embedded_image_valid(uri):
    """Check format signatures/structure; full decoding and visual review are separate."""
    if not uri.startswith('data:image/'):
        return False
    try:
        header, payload = uri.split(',', 1)
        if ';base64' not in header:
            return False
        data = base64.b64decode(payload, validate=True)
        mime = header[5:].split(';')[0].lower()
        if mime == 'image/png':
            return len(data) >= 45 and data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR' and all(struct.unpack('>II', data[16:24])) and data[-8:-4] == b'IEND'
        if mime in ('image/jpeg', 'image/jpg'):
            return len(data) > 30 and data.startswith(b'\xff\xd8') and data.endswith(b'\xff\xd9')
        if mime == 'image/gif':
            return len(data) > 13 and data[:6] in (b'GIF87a', b'GIF89a') and all(struct.unpack('<HH', data[6:10])) and data.endswith(b';')
        if mime == 'image/webp':
            return len(data) > 20 and data[:4] == b'RIFF' and data[8:12] == b'WEBP'
        if mime == 'image/svg+xml':
            svg = ET.fromstring(data)
            return svg.tag.split('}')[-1] == 'svg' and not any(n.tag.split('}')[-1] in ('script', 'foreignObject') or any(k.split('}')[-1] in ('href', 'src') and not v.startswith('#') for k, v in n.attrib.items()) for n in svg.iter())
    except (ValueError, TypeError, binascii.Error, ET.ParseError, struct.error):
        return False
    return False


def check_release(html_path, units_path, baseline_path, figures_path=None, tables_path=None, analysis_path=None, review_path=None):
    raw = Path(html_path).read_bytes()
    units, baseline = load(units_path), load(baseline_path)
    figures = load(figures_path) if figures_path else None
    tables = load(tables_path) if tables_path else None
    analysis = load(analysis_path) if analysis_path else None
    review = load(review_path) if review_path else {}
    validate_data(units, baseline, figures, tables, analysis, review)
    page = Page()
    page.feed(raw.decode('utf-8'))
    page.close()
    failures, limits, checks = [], [], {}
    digest = hashlib.sha256(raw).hexdigest()

    def check(name, ok, details=''):
        checks[name] = bool(ok)
        if not ok:
            failures.append({'check': name, 'details': details})

    check('unique_html_ids', len(page.ids) == len(set(page.ids)))
    missing = set(page.links) - set(page.ids)
    check('internal_anchor_targets', not missing, str(sorted(missing)))
    ids = [u['id'] for u in units]
    check('unit_ids_unique', len(ids) == len(set(ids)))
    check('baseline_required_units', ids == baseline['required_unit_ids'])
    check('rendered_scope_exact', page.unit_ids == ids)
    expected_owners = set(ids) | {f['id'] for f in figures or []}
    check('no_undeclared_originals', set(page.originals) <= expected_owners)
    check('rendered_unit_order', [x for x in page.ids if x in set(ids)] == ids)
    counts = {kind: sum(u['unit_type'] == kind for u in units) for kind in baseline['unit_counts']}
    check('baseline_unit_counts', counts == baseline['unit_counts'] and sum(counts.values()) == len(units))
    check('highlights_only_in_original', page.marks_in_original)
    for u in units:
        ident, original, translation = u['id'], u['original_text'], u.get('translation_zh', '')
        check(f'{ident}:original_exact', page.originals.get(ident) == [original])
        required = u.get('requires_translation', u['unit_type'] not in ('reference', 'metadata'))
        if required:
            check(f'{ident}:translation_done', bool(translation.strip()) and u['status'].get('translation') == 'done' and translation in page.translations.get(ident, []))
        check(f'{ident}:extraction_verified', u['status'].get('extraction') == 'verified')
        check(f'{ident}:source_check_recorded', u['status'].get('source_check') in ('page_verified', 'sampled'))
        check(f'{ident}:cross_reference_targets', all(x in page.ids for x in u.get('cross_references', [])))
        if u['unit_type'] in ('body', 'abstract'):
            role = u.get('rhetorical_function', '')
            roles = [role.get('primary', '')] + role.get('secondary', []) if isinstance(role, dict) else [role]
            check(f'{ident}:annotation_done', u['status'].get('annotation') in ('deep', 'brief') and bool(u.get('logical_role')) and bool(roles[0]))
            values = roles + [u.get('logical_role', ''), u.get('critical_commentary', '')]
            rendered = ' '.join(page.annotations.get(ident, []))
            check(f'{ident}:annotation_rendered', bool(rendered) and all(v in rendered for v in values))
        numeric_source = u.get('numeric_source_text')
        if numeric_source is None and not u.get('citation_refs'):
            numeric_source = original
        check(f'{ident}:numeric_source_available', isinstance(numeric_source, str) and bool(numeric_source.strip()))
        if required and numeric_source:
            def numbers(s):
                return set(re.findall(r'\d+(?:\.\d+)?', re.sub(r'(?<=\d),(?=\d{3}\b)', '', s)))
            missing_numbers = numbers(numeric_source) - numbers(translation)
            check(f'{ident}:numeric_literals_present', not missing_numbers, str(sorted(missing_numbers)))
        highlights = u.get('highlights', [])
        check(f'{ident}:highlights_exact_unique', all(original.count(h['quote']) == 1 for h in highlights))
        check(f'{ident}:highlights_rendered', sorted(page.marks.get(ident, [])) == sorted((h['quote'], h['category']) for h in highlights))
        positions = sorted((original.find(h['quote']), original.find(h['quote']) + len(h['quote'])) for h in highlights)
        check(f'{ident}:highlights_nonoverlapping', all(a[1] <= b[0] for a, b in zip(positions, positions[1:])))
        check(f'{ident}:highlight_density', len(highlights) <= 3 and sum(len(h['quote']) for h in highlights) <= len(original) * .25)
    if figures is not None:
        figure_ids = [f['id'] for f in figures]
        check('figure_count', len(figures) == baseline['figure_count'] and len(figure_ids) == len(set(figure_ids)))
        check('figure_originals_present', all(re.sub(r'\s+', '', f['original_text']) in [re.sub(r'\s+', '', value) for value in page.originals.get(f['id'], [])] for f in figures))
        check('figure_images_present', all(page.figure_images.get(f['id']) for f in figures))
        check('figure_ids_and_translations', all(f['id'] in page.ids and f['translation_zh'] in page.translations.get(f['id'], []) for f in figures))
    elif baseline['figure_count']:
        check('figure_data_provided', False)
    if tables is not None:
        table_ids = [t['id'] for t in tables]
        check('table_count', len(tables) == baseline['table_count'] and len(table_ids) == len(set(table_ids)))
        check('table_ids_present', all(t['id'] in page.ids for t in tables))
        check('all_source_table_cells_exact', all(page.tables.get(t['id']) == t['rows'] for t in tables), 'Checks each table separately, including row boundaries.')
    elif baseline['table_count']:
        check('table_data_provided', False)
    reference_ids = baseline['reference_ids']
    check('reference_targets', len(reference_ids) == len(set(reference_ids)) and all(x in page.ids for x in reference_ids))
    check('references_nonempty', all(any(s.strip() for s in page.text_by_id.get(x, [])) for x in reference_ids))
    check('analysis_data_provided', analysis is not None)
    if analysis is not None:
        claims = analysis['claims']
        claim_ids = [c['id'] for c in claims]
        lookup = {u['id']: u for u in units}
        check('claim_ids_unique_and_rendered', bool(claims) and len(claim_ids) == len(set(claim_ids)) and all(x in page.ids for x in claim_ids))
        check('claim_source_targets', all(all(x in lookup for x in c['units']) for c in claims))
        check('claim_evidence_exact', bool(claims) and all(any(c['quote'] in lookup[x]['original_text'] for x in c['units'] if x in lookup) for c in claims))
    css = re.sub(r'/\*.*?\*/', '', '\n'.join(page.styles), flags=re.S)
    css_urls = [x.strip().strip('\"\'') for x in re.findall(r'url\(([^)]*)\)', css, re.I)]
    check('no_external_runtime_resources', all(x.startswith(('data:', '#')) for x in page.resources + css_urls) and not re.search(r'@\s*import\b', css, re.I))
    check('all_images_embedded_nonempty', all(x.startswith('data:image/') for x in page.images))
    check('embedded_image_encoding', all(embedded_image_valid(x) for x in page.images), 'Signature/structure checks, not a full image decode or visual review.')
    check('review_matches_final_sha256', review.get('file_sha256') == digest)
    check('content_review_recorded', review.get('content_review', {}).get('status') == 'passed')
    browser = review.get('browser_review', {})
    if browser.get('status') != 'passed':
        if browser.get('status') in ('blocked', 'unavailable') and browser.get('reason') and browser.get('plan'):
            limits.append(browser)
        else:
            check('browser_review_or_documented_limit', False)
    verdict = 'checkpoint' if failures else 'ready_with_verification_limits' if limits else 'ready'
    return {'schema_version': 2, 'verdict': verdict, 'file_sha256': digest, 'checks': checks, 'failures': failures, 'verification_limits': limits, 'boundary': 'Static source/structure equality and recorded review evidence. Does not prove translation semantics, source correctness, pixel visibility or browser rendering.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('html', 'units', 'baseline', 'report'):
        parser.add_argument('--' + key, required=True, type=Path)
    for key in ('figures', 'tables', 'analysis', 'review'):
        parser.add_argument('--' + key, type=Path)
    args = parser.parse_args()
    inputs = [args.html, args.units, args.baseline, args.figures, args.tables, args.analysis, args.review]
    if any(p is not None and p.resolve() == args.report.resolve() for p in inputs):
        print('Report path must not overwrite an input file.', file=sys.stderr)
        return 2
    code = 0
    try:
        report = check_release(args.html, args.units, args.baseline, args.figures, args.tables, args.analysis, args.review)
        code = 1 if report['failures'] else 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        report = {'schema_version': 2, 'verdict': 'not_auditable', 'checks': {}, 'failures': [{'check': 'input_data', 'details': str(exc)}], 'verification_limits': []}
        code = 2
    try:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except OSError as exc:
        print(f'Cannot write audit report: {exc}', file=sys.stderr)
        return 2
    print(f"{report['verdict']}: {sum(report['checks'].values())}/{len(report['checks'])} checks; {len(report['failures'])} failures")
    return code


if __name__ == '__main__':
    raise SystemExit(main())
