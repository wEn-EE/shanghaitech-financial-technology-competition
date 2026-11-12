"""SYNTHETIC, deterministic news features. Python standard library only."""
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import re

RULE_VERSION = 'synthetic-lexicon-v1'
LEXICON = {'盈利增长': 1, '业绩改善': 1, '亏损扩大': -1, '违约': -1}

@dataclass(frozen=True)
class News:
    id: str
    story: str
    revision: int
    event_time: int
    published: int
    available: int
    source: str
    asset: str
    text: str
    withdrawn: bool = False


def classify(text):
    evidence = []
    # Three-character lookback is deliberately limited, not general negation parsing.
    for phrase, polarity in LEXICON.items():
        for m in re.finditer(re.escape(phrase), text):
            prefix = text[max(0, m.start()-3):m.start()]
            uncertain = any(x in prefix for x in ('可能', '传闻'))
            negated = any(x in prefix for x in ('未', '没有', '否认'))
            evidence.append({'start': m.start(), 'end': m.end(),
                             'text': m.group(), 'polarity': polarity,
                             'negated': negated, 'uncertain': uncertain})
    active = [e['polarity'] for e in evidence if not e['negated'] and not e['uncertain']]
    score = sum(active)/len(active) if active else None
    return {'score': score, 'evidence': evidence,
            'status': 'SCORED' if active else 'UNKNOWN',
            'rule_version': RULE_VERSION}


def snapshot(news, cutoff, asset, half_life=10):
    if half_life <= 0:
        raise ValueError('half_life must be positive')
    if len({n.id for n in news}) != len(news):
        raise ValueError('duplicate input id')
    latest = {}
    for n in news:
        if n.available < n.published or n.revision < 1:
            raise ValueError('invalid chronology or revision')
        if n.available > cutoff:
            continue
        key = (n.story, n.source)
        rank = (n.revision, n.available, n.id)
        if key not in latest or rank > (latest[key].revision, latest[key].available, latest[key].id):
            latest[key] = n
    chosen = {}
    for n in latest.values():
        if n.withdrawn or n.asset != asset:
            continue
        digest = hashlib.sha256(n.text.encode('utf-8')).hexdigest()
        # Known synthetic story IDs, not a learned clustering system.
        key = (n.story, digest)
        if key not in chosen or (n.available, n.id) < (chosen[key].available, chosen[key].id):
            chosen[key] = n
    details = []
    numerator = denominator = sum_sq = 0.0
    for n in sorted(chosen.values(), key=lambda n: n.id):
        pred = classify(n.text)
        weight = 2 ** (-(cutoff-n.available)/half_life)
        details.append({'id': n.id, 'weight': weight, **pred})
        if pred['score'] is not None:
            numerator += weight*pred['score']
            denominator += weight
            sum_sq += weight**2
    return {'cutoff': cutoff, 'asset': asset, 'documents': details,
            'unique_count': len(details),
            'scored_count': sum(d['score'] is not None for d in details),
            'sentiment': numerator/denominator if denominator else None,
            'weighted_mass': denominator,
            'weight_effective_count': denominator**2/sum_sq if sum_sq else 0,
            'rule_version': RULE_VERSION}


def sample():
    return [
        News('a1', 'A', 1, 1, 2, 5, 'wire', 'EQ_DEMO', '甲公司盈利增长。'),
        News('copy', 'A', 1, 1, 3, 6, 'portal', 'EQ_DEMO', '甲公司盈利增长。'),
        News('b1', 'B', 1, 3, 4, 8, 'wire', 'EQ_DEMO', '乙公司亏损扩大。'),
        News('c1', 'C', 1, 4, 5, 9, 'wire', 'EQ_DEMO', '丙公司未违约。'),
        News('d1', 'D', 1, 0, 1, 12, 'wire', 'EQ_DEMO', '丁公司业绩改善。'),
        News('b2', 'B', 2, 3, 13, 15, 'wire', 'EQ_DEMO', '更正：乙公司盈利增长。'),
        News('a2', 'A', 2, 1, 16, 18, 'wire', 'EQ_DEMO', '', True),
    ]


def main():
    news = sample()
    result = {'data_kind': 'SYNTHETIC', 'input': [asdict(n) for n in news],
              'snapshots': [snapshot(news, t, 'EQ_DEMO') for t in (4, 10, 14, 16, 20)]}
    out = Path(__file__).parent/'runs'/datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ')
    out.mkdir(parents=True)
    data = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    (out/'results.json').write_text(data, encoding='utf-8')
    manifest = {'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'result_sha256': hashlib.sha256((out/'results.json').read_bytes()).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(out)
    for s in result['snapshots']:
        print(s['cutoff'], s['unique_count'], s['scored_count'], s['sentiment'])

if __name__ == '__main__':
    main()
