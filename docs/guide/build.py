"""Build offline HTML guides from locale data; no network or extra dependencies."""

import html
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent
LANGUAGES = {"ru": "Русский", "en": "English", "es": "Español", "pt-BR": "Português", "zh-Hans": "简体中文", "fr": "Français", "de": "Deutsch"}


def escape(value: str) -> str:
    return html.escape(str(value), quote=True)


def snippets(items: list, kind: str, section: str, ui: dict) -> str:
    result = []
    for index, item in enumerate(items):
        code_id = f"{section}-{kind}-{index}"
        result.append(f'<div class="snippet {kind}"><div class="snippet-head"><h3>{escape(item["label"])}</h3><button type="button" class="copy" data-copy="{code_id}" aria-label="{escape(ui["copy"] + " " + item["label"])}">{escape(ui["copy"])}</button></div><pre id="{code_id}"><code>{escape(item["text"])}</code></pre></div>')
    return "".join(result)


def content(data: dict) -> str:
    ui = data["ui"]
    parts = [f'<noscript><p class="note">{escape(ui["noscript"])}</p></noscript><p class="eyebrow">{escape(ui["documentation"])}</p><h1>{escape(data["title"])}</h1><p class="subtitle">{escape(data["subtitle"])}</p><div class="intro">']
    parts += [f'<p>{escape(p)}</p>' for p in data["intro"]]
    parts.append(f'</div><p class="note">{escape(ui["screenNote"])}</p>')
    for index, section in enumerate(data["sections"]):
        parts.append(f'<section class="section" id="{escape(section["id"])}"><h2><span class="number">{index+1:02}</span>{escape(section["title"])}</h2>')
        parts += [f'<p>{escape(p)}</p>' for p in section["paragraphs"]]
        if section.get("steps"):
            parts.append('<ol>' + ''.join(f'<li>{escape(s)}</li>' for s in section["steps"]) + '</ol>')
        parts.append(snippets(section.get("code", []), "command", section["id"], ui))
        parts.append(snippets(section.get("prompts", []), "prompt", section["id"], ui))
        for figure in section.get("figures", []):
            image = PROJECT / 'docs/guide' / figure["src"]
            if not image.is_file():
                raise ValueError(f"Missing guide screenshot: {image}")
            parts.append(f'<figure><a href="{escape(figure["src"])}" target="_blank" rel="noopener"><img src="{escape(figure["src"])}" alt="{escape(figure["alt"])}" loading="lazy" decoding="async" width="1440" height="1000"></a><figcaption>{escape(figure["caption"])}</figcaption></figure>')
        parts.append('</section>')
    parts.append(f'<section class="section" id="glossary"><h2>{escape(ui["glossary"])}</h2><dl>'+''.join(f'<dt>{escape(item["term"])}</dt><dd>{escape(item["description"])}</dd>' for item in data['glossary'])+'</dl></section>')
    parts.append(f'<footer><p>{escape(ui["localGuide"])}</p><div class="resources"><a href="assets/verified-projections.html">mt_truck/v001 · iso/front/back/left/right/top/bottom</a><a href="resources/PROJECTION_CONTRACT.md">PROJECTION_CONTRACT.md</a><a href="resources/sketch_brief.example.yaml">sketch_brief.example.yaml</a><a href="resources/sketch_template.yaml">sketch_template.yaml</a><a href="resources/generation_brief.example.yaml">generation_brief.example.yaml</a></div><a class="back" href="#content">{escape(ui["top"])}</a></footer>')
    return ''.join(parts)


def main() -> None:
    locales = {code: json.loads((ROOT / 'locales' / f'{code}.json').read_text(encoding='utf-8')) for code in LANGUAGES}
    canonical_ids = [section["id"] for section in locales["en"]["sections"]]
    for code, data in locales.items():
        if [s["id"] for s in data["sections"]] != canonical_ids:
            raise ValueError(f"Section mismatch for locale {code}")
    resources = ROOT / 'resources'
    resources.mkdir(exist_ok=True)
    for source in ('PROJECTION_CONTRACT.md', 'templates/sketch_brief.example.yaml', 'templates/sketch_template.yaml', 'templates/generation_brief.example.yaml'):
        path = PROJECT / 'impressor' / source
        shutil.copy2(path, resources / path.name)
    contract_copy = resources / 'PROJECTION_CONTRACT.md'
    contract_copy.write_text(contract_copy.read_text(encoding='utf-8').replace('](SKETCH_GENERATION.md)', '](../index.html#imagegen)'), encoding='utf-8')
    template = (ROOT / 'template.html').read_text(encoding='utf-8')
    embedded = json.dumps(locales, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    for code, data in locales.items():
        values = {
            'LANG': code, 'TITLE': escape(data['title']), 'DESCRIPTION': escape(data['subtitle']),
            'SKIP': escape(data['ui']['top']), 'LANGUAGE_LABEL': escape(data['ui']['language']),
            'PRINT': escape(data['ui']['print']), 'CONTENTS': escape(data['ui']['contents']),
            'OPTIONS': ''.join(f'<option value="{key}"'+(' selected' if key==code else '')+f'>{name}</option>' for key,name in LANGUAGES.items()),
            'TOC': ''.join(f'<a href="#{escape(s["id"])}">{i+1:02} · {escape(s["title"])}</a>' for i,s in enumerate(data['sections'])),
            'CONTENT': content(data), 'DATA': embedded,
        }
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace(f'@@{key}@@', value)
        if '@@' in rendered:
            raise ValueError('Unresolved template placeholder')
        (ROOT / f'{code}.html').write_text(rendered, encoding='utf-8')
        if code == 'ru':
            (ROOT / 'index.html').write_text(rendered, encoding='utf-8')
    print(f'Built {len(locales)} languages, {len(canonical_ids)} sections; open docs/guide/index.html')


if __name__ == '__main__':
    main()
