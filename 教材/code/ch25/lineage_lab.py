"""SYNTHETIC lineage lab. Standard library, single-process SQLite."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, Context, localcontext
import hashlib
import json
import platform
import sqlite3
import uuid

SCHEMA = '''
CREATE TABLE IF NOT EXISTS artifacts(
 hash TEXT PRIMARY KEY, body BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS runs(
 id TEXT PRIMARY KEY, recipe_hash TEXT NOT NULL, status TEXT NOT NULL,
 manifest_hash TEXT, error TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS one_success ON runs(recipe_hash)
 WHERE status='SUCCESS';
CREATE TABLE IF NOT EXISTS edges(
 run_id TEXT NOT NULL REFERENCES runs(id), parent TEXT NOT NULL REFERENCES artifacts(hash),
 child TEXT NOT NULL REFERENCES artifacts(hash), role TEXT NOT NULL,
 PRIMARY KEY(run_id,parent,child,role));
'''

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')

def digest(body):
    return hashlib.sha256(body).hexdigest()

def connect(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(SCHEMA)
    return db

def put(db, body):
    key = digest(body)
    old = db.execute('SELECT body FROM artifacts WHERE hash=?', (key,)).fetchone()
    if old is not None and bytes(old[0]) != body:
        raise ValueError('existing artifact corrupted or collision')
    db.execute('INSERT OR IGNORE INTO artifacts VALUES (?,?)', (key, body))
    return key

def read(db, key):
    row = db.execute('SELECT body FROM artifacts WHERE hash=?', (key,)).fetchone()
    if row is None or digest(bytes(row[0])) != key:
        raise ValueError('missing or corrupted artifact')
    return bytes(row[0])

def verify(db, manifest_hash):
    manifest = json.loads(read(db, manifest_hash))
    for key in manifest['artifacts'].values():
        read(db, key)
    recipe = json.loads(read(db, manifest['artifacts']['recipe']))
    if recipe['raw'] != manifest['artifacts']['raw'] or recipe['code'] != manifest['artifacts']['code']:
        raise ValueError('lineage mismatch')
    return json.loads(read(db, manifest['artifacts']['result']))

def compute(raw, cutoff, threshold):
    rows = json.loads(raw)
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('duplicate row id')
    selected, audit = [], []
    for row in rows:
        if not isinstance(row['ready'], int):
            raise ValueError('ready must be integer')
        value = Decimal(row['value'])
        if not value.is_finite():
            raise ValueError('nonfinite value')
        if row['ready'] <= cutoff:
            selected.append(row)
        else:
            audit.append({'id': row['id'], 'reason': 'NOT_YET_AVAILABLE'})
    selected.sort(key=lambda r: r['id'])
    with localcontext(Context(prec=28)):
        mean = sum((Decimal(r['value']) for r in selected), Decimal(0))/len(selected) if selected else None
    result = {'cutoff': cutoff, 'mean': str(mean) if mean is not None else None,
              'state': 'UNKNOWN' if mean is None else ('HIGH' if mean > threshold else 'LOW'),
              'selected_ids': [r['id'] for r in selected]}
    return selected, audit, result

def pipeline(db, raw, cutoff, threshold='2', fail=False):
    bound = Decimal(threshold)
    if not bound.is_finite() or not isinstance(cutoff, int):
        raise ValueError('invalid configuration')
    code = Path(__file__).read_bytes()
    recipe = {'schema': 1, 'raw': digest(raw), 'code': digest(code),
              'parameters': {'cutoff': cutoff, 'threshold': threshold},
              'environment': {'python': platform.python_version(),
                              'sqlite': sqlite3.sqlite_version, 'decimal_context': 'prec=28,rounding=ROUND_HALF_EVEN'},
              'semantics': 'ready_le_cutoff_decimal_v1'}
    recipe_body = canonical(recipe)
    key = digest(recipe_body)
    cached = db.execute("SELECT manifest_hash FROM runs WHERE recipe_hash=? AND status='SUCCESS'", (key,)).fetchone()
    if cached:
        return {'cached': True, 'recipe_hash': key, 'manifest_hash': cached[0],
                'result': verify(db, cached[0])}
    run_id = str(uuid.uuid4())
    with db:
        db.execute('INSERT INTO runs VALUES (?,?,?,NULL,NULL)', (run_id,key,'RUNNING'))
    try:
        selected, audit, result = compute(raw, cutoff, bound)
        with db:
            artifacts = {'raw': put(db,raw), 'code': put(db,code),
                         'recipe': put(db,recipe_body), 'selected': put(db,canonical(selected)),
                         'audit': put(db,canonical(audit)), 'result': put(db,canonical(result))}
            manifest = put(db,canonical({'schema':1,'artifacts':artifacts}))
            for role, parent in artifacts.items():
                db.execute('INSERT INTO edges VALUES (?,?,?,?)', (run_id,parent,manifest,role))
            if fail:
                raise RuntimeError('injected failure before commit')
            db.execute("UPDATE runs SET status='SUCCESS',manifest_hash=? WHERE id=?", (manifest,run_id))
        return {'cached': False, 'recipe_hash':key,'manifest_hash':manifest,'result':result}
    except Exception as exc:
        with db:
            db.execute("UPDATE runs SET status='FAILED',error=? WHERE id=?", (type(exc).__name__,run_id))
        raise

def sample():
    return canonical([{'id':'a','ready':1,'value':'1'},
                      {'id':'b','ready':3,'value':'3'},
                      {'id':'c','ready':8,'value':'8'}])

def main():
    out=Path(__file__).parent/'runs'/datetime.now(timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ')
    out.mkdir(parents=True)
    db=connect(out/'lineage.sqlite')
    a=pipeline(db,sample(),3)
    b=pipeline(db,sample(),3)
    c=pipeline(db,sample(),8)
    report={'data_kind':'SYNTHETIC','first':a,'retry':b,'later':c,
            'integrity':db.execute('PRAGMA integrity_check').fetchone()[0]}
    (out/'report.json').write_bytes(canonical(report))
    db.close()
    print(out)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

