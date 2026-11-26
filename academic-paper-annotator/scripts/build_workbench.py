#!/usr/bin/env python3
"""Render prepared, reviewed paper data. Does not extract or translate papers."""
import argparse
import base64
import html
import json
import mimetypes
from pathlib import Path
from validate_release import validate_data, DataError

ASSETS = Path(__file__).resolve().parents[1] / 'assets'

def load(root, name, default=None):
    path = root / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def h(value):
    return html.escape(str(value))

def image(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Image path must stay within the data directory.')
    mime = mimetypes.guess_type(path.name)[0]
    if mime not in ('image/png', 'image/jpeg', 'image/svg+xml', 'image/webp', 'image/gif'):
        raise ValueError('Unsupported image format: ' + str(relative))
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')

def original(unit):
    value = unit['original_text']
    pieces, cursor = [], 0
    for highlight in sorted(unit.get('highlights', []), key=lambda x: value.find(x['quote'])):
        quote = highlight['quote']
        if value.count(quote) != 1:
            raise ValueError(unit['id'] + ': highlight must match once')
        start = value.index(quote)
        if start < cursor:
            raise ValueError(unit['id'] + ': overlapping highlights')
        pieces += [h(value[cursor:start]), '<mark class="hl ' + h(highlight['category']) + '" title="' + h(highlight['category']) + '">' + h(quote) + '</mark>']
        cursor = start + len(quote)
    return ''.join(pieces) + h(value[cursor:])

def build(root, output):
    paper = load(root, 'paper.json')
    units, figures, tables = load(root, 'units.json'), load(root, 'figures.json', []), load(root, 'tables.json', [])
    analysis = load(root, 'analysis.json', {})
    if not isinstance(paper, dict) or not isinstance(units, list) or not units:
        raise ValueError('paper.json and a nonempty units.json are required')
    validate_data(units, load(root, 'baseline.json'), figures, tables, analysis, {})
    for key in ('title', 'notice', 'source_note'):
        if not isinstance(paper.get(key), str) or not paper[key].strip():
            raise ValueError('paper.' + key + ' must be nonempty text')
    # Preserve the source sequence, even when heading labels recur later.
    sections = []
    for unit in units:
        label = unit.get('section', '正文')
        key = unit.get('section_id', label)
        if not sections or sections[-1]['key'] != key:
            proposed = unit.get('section_id', f'S{len(sections)+1:03}')
            existing = {section['id'] for section in sections}
            dom_id = proposed if proposed not in existing else f'{proposed}-part{len(sections)+1}'
            sections.append({'id': dom_id, 'key': key, 'label': label, 'units': []})
        sections[-1]['units'].append(unit)
    nav = ''.join('<a href="#' + h(section['id']) + '">' + h(section['label']) + '</a>' for section in sections)
    controls = '''<div id="controls" hidden class="tools print-hide"><nav aria-label="章节导航">''' + nav + '''<a href="#claims">证据矩阵</a><a href="#notes">来源与检查</a></nav><div class="row"><label>模式 <select id="mode"><option value="bilingual">英中对照</option><option value="english">仅英文</option><option value="focus">批注重点</option></select></label><label><input id="annotations" type="checkbox" checked>批注</label><label><input id="deep" type="checkbox">仅深读</label><button id="expand">全部展开</button><button id="collapse">全部折叠</button><button id="print">打印</button><span id="current" class="meta"></span><progress id="progress" max="100" value="0" aria-label="浏览进度"></progress><span id="progress-text" class="meta"></span></div><div class="row"><label for="search">搜索</label><input id="search" type="search"><button id="search-go">查找</button><button id="prev">上一个</button><button id="next">下一个</button><button id="clear">清除</button><span id="results" aria-live="polite">搜索原文、译文与批注</span></div><div class="legend">''' + ''.join(f'<label><input data-hl="{key}" type="checkbox" checked>{label}</label>' for key, label in [('claim', '主张'), ('concept', '概念'), ('evidence', '证据'), ('limitation', '局限'), ('method', '方法')]) + '</div></div>'
    body = '<section id="guide"><h2>导读</h2><p class="notice">' + h(paper['notice']) + '</p><p>' + h(paper.get('guide', '')) + '</p><p class="meta">正文状态：' + str(sum(u.get('status', {}).get('translation') == 'done' for u in units)) + ' / ' + str(len(units)) + ' 个单元译文完成。最终验证以对应文件摘要的 release-report.json 为准。</p></section>'
    for run in sections:
        section = run['label']
        body += '<section id="' + h(run['id']) + '"><h2>' + h(section) + '</h2>'
        for unit in run['units']:
            role = unit.get('rhetorical_function', '')
            if isinstance(role, dict):
                role = ' / '.join([role.get('primary', '')] + role.get('secondary', []))
            location = unit.get('source_location', {})
            if not isinstance(location, dict):
                raise ValueError(unit['id'] + ': source_location must be an object')
            source = ' · '.join(str(k) + ': ' + str(v) for k, v in location.items() if v is not None)
            source_meta = ' · 来源：' + h(source) if source else ''
            body += f'<article class="unit" id="{h(unit["id"])}" data-depth="{h(unit.get("depth", "brief"))}" data-section="{h(section)}" data-search><div><div class="meta">{h(unit["id"])} · {h(unit.get("depth", "brief"))}{source_meta}</div><p class="original" lang="en">{original(unit)}</p>'
            if unit.get('image_path'):
                body += '<img class="figure-image" src="' + image(root, unit['image_path']) + '" alt="' + h(unit['original_text']) + '">'
            body += '<div class="translation" lang="zh-CN">' + h(unit.get('translation_zh', '')) + '</div></div><aside><details class="annotation" open><summary>批注</summary><p><strong>功能：</strong>' + h(role) + '</p><p><strong>分析者重构：</strong>' + h(unit.get('logical_role', '')) + '</p><p>' + h(unit.get('critical_commentary', '')) + '</p></details></aside></article>'
        if section in analysis.get('section_reviews', {}):
            body += '<aside class="section-review"><h3>章节总结 · 分析者重构</h3><p>' + h(analysis['section_reviews'][section]) + '</p></aside>'
        body += '</section>'
    for f in figures:
        body += '<figure id="' + h(f['id']) + '" class="figure" data-search><h3>' + h(f['id']) + '</h3><img class="figure-image" src="' + image(root, f['image_path']) + '" alt="' + h(f['translation_zh']) + '"><figcaption><p class="original" lang="en">' + h(f['original_text']) + '</p><div class="translation">' + h(f['translation_zh']) + '</div></figcaption></figure>'
    for t in tables:
        body += '<section id="' + h(t['id']) + '" data-search><h3>' + h(t.get('title', t['id'])) + '</h3><div class="table-scroll"><table><caption>' + h(t.get('caption', '')) + '</caption>'
        for r, row in enumerate(t['rows']):
            body += '<tr>'
            for c, value in enumerate(row):
                tag = 'th' if r == 0 or c == 0 else 'td'
                translated = t.get('label_translations', {}).get(value)
                body += '<' + tag + (' scope="col"' if r == 0 else ' scope="row"' if c == 0 else '') + '><span class="cell-original">' + h(value) + '</span>' + ('<span class="cn">' + h(translated) + '</span>' if translated else '') + '</' + tag + '>'
            body += '</tr>'
        body += '</table></div></section>'
    body += '<section id="claims"><h2>主张—证据矩阵 · 分析者重构</h2><div class="table-scroll"><table><tr><th>主张</th><th>来源与逐字证据</th><th>支持范围</th></tr>'
    for claim in analysis.get('claims', []):
        body += '<tr id="' + h(claim['id']) + '"><th scope="row">' + h(claim.get('claim', claim['id'])) + '</th><td><blockquote lang="en">' + h(claim['quote']) + '</blockquote>' + '、'.join('<a href="#' + h(i) + '">' + h(i) + '</a>' for i in claim['units']) + '</td><td>' + h(claim.get('scope', '')) + '</td></tr>'
    body += '</table></div></section><section id="argument"><h2>论证关系 · 分析者重构</h2>'
    relations = analysis.get('relations', [])
    nodes = list(dict.fromkeys(v for r in relations for v in (r['from'], r['to'])))
    layers, todo = {}, set(nodes)
    while todo:
        ready = [n for n in nodes if n in todo and all(r['from'] in layers for r in relations if r['to'] == n)]
        if not ready:
            raise ValueError('Argument relations must form a DAG; revise the dependency representation.')
        for n in ready:
            layers[n] = max([layers[r['from']] + 1 for r in relations if r['to'] == n] or [0])
            todo.remove(n)
    if nodes:
        slots, positions = {}, {}
        for n in nodes:
            layer = layers[n];row = slots.get(layer, 0);slots[layer] = row + 1;positions[n] = (20 + layer * 260, 30 + row * 100)
        width, height = 260 * (max(layers.values()) + 1), max(slots.values()) * 100 + 30
        body += f'<div class="graph-scroll"><svg viewBox="0 0 {width} {height}" role="img" aria-label="分析者重构的论证依赖"><defs><marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8Z" fill="#536277"/></marker></defs>'
        for r in relations:
            x,y = positions[r['from']];xx,yy = positions[r['to']]
            body += f'<path d="M{x+210} {y+28} L{xx-6} {yy+28}" stroke="#536277" fill="none" marker-end="url(#graph-arrow)"/>'
        for n in nodes:
            x,y = positions[n];label = analysis.get('graph_labels', {}).get(n,n)
            body += f'<a href="#{h(n)}"><rect x="{x}" y="{y}" width="210" height="56" rx="3" fill="#f0ece2" stroke="#14253d"/><text x="{x+105}" y="{y+34}" text-anchor="middle" font-size="14">{h(label)}</text></a>'
        body += '</svg></div>'
    body += '<ul>'
    for relation in relations:
        body += '<li><a href="#' + h(relation['from']) + '">' + h(relation['from']) + '</a> ' + h(relation['relation']) + ' <a href="#' + h(relation['to']) + '">' + h(relation['to']) + '</a></li>'
    body += '</ul></section>'
    for title, key in [('整体评价', 'evaluation'), ('学习迁移', 'learning'), ('后续研究问题', 'questions')]:
        body += '<section><h2>' + title + '</h2><ul>' + ''.join('<li>' + h(v) + '</li>' for v in analysis.get(key, [])) + '</ul></section>'
    body += '<section id="references"><h2>参考文献与来源</h2><ol>' + ''.join('<li id="' + h(r['id']) + '">' + h(r['citation']) + '</li>' for r in paper.get('references', [])) + '</ol></section>'
    body += '<section id="notes"><h2>Source &amp; Analysis Notes</h2><p>' + h(paper['source_note']) + '</p><p>构建器只预渲染准备好的数据，不提取或翻译论文，也不会生成审阅通过声明。重建后，旧文件摘要不匹配时应重新审阅。</p></section>'
    css, js = (ASSETS / 'workbench.css').read_text(encoding='utf-8'), (ASSETS / 'workbench.js').read_text(encoding='utf-8')
    final = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + h(paper['title']) + '</title><style>' + css + '</style></head><body><a class="skip" href="#main">跳过导航</a><header><div class="eyebrow">ACADEMIC PAPER ANNOTATOR</div><h1>' + h(paper['title']) + '</h1><p>' + h(paper.get('authors', '')) + '</p></header>' + controls + '<main id="main"><p class="no-js-note">JavaScript 关闭时仍可阅读全部内容。</p>' + body + '</main><script>' + js + '</script></body></html>'
    output.write_text(final, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.suffix.lower() not in ('.html', '.htm'):
            raise ValueError('Output must be an HTML file.')
        if args.output.resolve() in {p.resolve() for p in args.data.glob('*.json')}:
            raise ValueError('Output must not overwrite input data.')
        build(args.data, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')
    print('Built ' + str(args.output))

if __name__ == '__main__':
    main()
