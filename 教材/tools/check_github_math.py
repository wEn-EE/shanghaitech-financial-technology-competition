"""Verify formula transport through GitHub's official Markdown renderer.

Usage: python check_github_math.py CHAPTER.md [CHAPTER.md ...]
Only sends the explicitly selected Markdown to api.github.com/markdown.
Does not publish files, create comments, or change repository contents.
This checks recognition/transport, not browser layout or mathematical truth.
"""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
import argparse
import json
import re

from format_math import transform_document


class FormulaHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current = None
        self.formulas = []

    def handle_starttag(self, tag, attrs):
        if tag == 'math-renderer':
            self.current = []
        elif tag == 'br' and self.current is not None:
            self.current.append('\n')

    def handle_endtag(self, tag):
        if tag == 'math-renderer' and self.current is not None:
            self.formulas.append(''.join(self.current))
            self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)


def formula_key(value):
    return re.sub(r'\s+', '', value.strip().strip('$'))


def compare(text, rendered_html):
    _, records = transform_document(text)
    parser = FormulaHTML()
    parser.feed(rendered_html)
    expected = Counter(formula_key(item['source']) for item in records)
    received = Counter(formula_key(item) for item in parser.formulas)
    return {'expected': sum(expected.values()), 'recognized': sum(received.values()),
            'missing_or_changed': list((expected - received).elements()),
            'unexpected_or_changed': list((received - expected).elements())}


def render(text):
    payload = json.dumps({'text': text, 'mode': 'gfm'}).encode('utf-8')
    request = Request('https://api.github.com/markdown', data=payload, headers={
        'User-Agent': 'Textbook-math-transport-check/1.0',
        'Content-Type': 'application/json', 'Accept': 'application/vnd.github+json'})
    with urlopen(request, timeout=30) as response:
        return response.read().decode('utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', type=Path, nargs='+')
    args = parser.parse_args()
    failed = False
    for path in args.files:
        text = path.read_text(encoding='utf-8')
        report = compare(text, render(text))
        print(json.dumps({'file': str(path), **report}, ensure_ascii=False))
        failed |= bool(report['missing_or_changed'] or report['unexpected_or_changed'])
    raise SystemExit(1 if failed else 0)
