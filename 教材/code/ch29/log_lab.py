"""Replay the chapter 28 opening window; only the standard library is required."""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

TOPIC = "market.quotes.ch29.v1"
PART = {"EQ_DEMO": 0, "BOND_DEMO": 0, "FX_DEMO": 1, "GOLD_DEMO": 1}
COLUMNS = ("asset", "event_s", "revision", "ready_s", "price_atoms", "scale", "seed_uid")
SCHEMA = """
CREATE TABLE IF NOT EXISTS receipt(g TEXT,t TEXT,p INT,o INT,k BLOB,raw BLOB,status TEXT,
 PRIMARY KEY(g,t,p,o));
CREATE TABLE IF NOT EXISTS event(g TEXT,asset TEXT,s INT,r INT,body TEXT,
 PRIMARY KEY(g,asset,s,r));
"""
LOG_SCHEMA = """
CREATE TABLE log(p INT,o INT,k BLOB,raw BLOB,PRIMARY KEY(p,o));
CREATE TABLE progress(g TEXT,p INT,n INT,PRIMARY KEY(g,p));
"""


def messages(source):
    uri = source.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        rows = db.execute("SELECT asset,event_s,revision,ready_s,price_atoms,scale,seed_uid "
                          "FROM quotes WHERE event_s IN (0,60) ORDER BY ready_s,asset").fetchall()
    for row in rows:
        obj = dict(zip(COLUMNS, row), schema=1, source="SYNTHETIC")
        yield row[0].encode(), json.dumps(obj, sort_keys=True).encode()
        if row[:3] == ("EQ_DEMO", 0, 1):
            yield row[0].encode(), json.dumps(obj, sort_keys=True).encode()


def apply(db, group, topic, part, offset, key, raw):
    """One SQLite transaction records the physical receipt and its business effect."""
    with db:
        old = db.execute("SELECT k,raw FROM receipt WHERE g=? AND t=? AND p=? AND o=?",
                         (group,topic,part,offset)).fetchone()
        if old is not None:
            if old != (key,raw):
                raise ValueError("payload changed at an existing log coordinate")
            return "REPLAY"
        try:
            obj = json.loads(raw)
            if (not isinstance(obj,dict) or set(obj) != set(COLUMNS) | {"schema","source"}
                    or type(obj["schema"]) is not int or obj["schema"] != 1
                    or obj["source"] != "SYNTHETIC" or obj["asset"] not in PART
                    or obj["asset"].encode() != key or PART[obj["asset"]] != part
                    or any(type(obj[f]) is not int or not 0 <= obj[f] < 2**63
                           for f in ("event_s","ready_s","revision","price_atoms","scale"))
                    or obj["ready_s"] < obj["event_s"] or obj["revision"] < 1
                    or not isinstance(obj["seed_uid"],str) or not obj["seed_uid"]):
                raise ValueError("contract")
        except (ValueError, TypeError, KeyError):
            status = "INVALID"
        else:
            identity = (group,obj["asset"],obj["event_s"],obj["revision"])
            body = json.dumps(obj, sort_keys=True)
            previous = db.execute("SELECT body FROM event WHERE g=? AND asset=? AND s=? AND r=?",
                                  identity).fetchone()
            if previous is None:
                db.execute("INSERT INTO event VALUES (?,?,?,?,?)", (*identity,body))
                status = "ACCEPTED"
            else:
                status = "DUPLICATE" if previous[0] == body else "CONFLICT"
        db.execute("INSERT INTO receipt VALUES (?,?,?,?,?,?,?)",
                   (group,topic,part,offset,key,raw,status))
    return status


def work(path, group, fault):
    with closing(sqlite3.connect(path)) as db:
        for p in (0,1):
            row = db.execute("SELECT n FROM progress WHERE g=? AND p=?", (group,p)).fetchone()
            start = row[0] if row else 0
            for o,k,raw in db.execute("SELECT o,k,raw FROM log WHERE p=? AND o>=? ORDER BY o",
                                      (p,start)).fetchall():
                if fault == "early" and p == 0 and o == 0:
                    with db:
                        db.execute("INSERT OR REPLACE INTO progress VALUES (?,?,?)",(group,p,o+1))
                    os._exit(73)
                status = apply(db,group,TOPIC,p,o,k,raw)
                if fault == "late" and p == 0 and o == 0:
                    os._exit(73)
                with db:
                    db.execute("INSERT OR REPLACE INTO progress VALUES (?,?,?)",(group,p,o+1))
                if status == "REPLAY":
                    print("replayed",group,p,o,flush=True)


def experiment(source, path):
    with closing(sqlite3.connect(path)) as db:
        db.executescript(SCHEMA + LOG_SCHEMA)
        ends = [0,0]
        with db:
            for k,raw in messages(source):
                p = PART[k.decode()]
                db.execute("INSERT INTO log VALUES (?,?,?,?)",(p,ends[p],k,raw))
                ends[p] += 1
        for group,fault in (("audit","none"),("features","late"),("unsafe","early")):
            if fault != "none":
                child = subprocess.run([sys.executable,__file__,"--worker",str(path),group,fault])
                if child.returncode != 73:
                    raise RuntimeError("unexpected worker exit")
            work(path,group,"none")
        return dict(ends=ends, receipts=db.execute(
            "SELECT g,status,count(*) FROM receipt GROUP BY g,status ORDER BY g,status").fetchall(),
            next_offsets=db.execute("SELECT g,p,n FROM progress ORDER BY g,p").fetchall(),
            skipped=db.execute("SELECT p,o FROM log EXCEPT SELECT p,o FROM receipt WHERE g='unsafe'").fetchall())


if __name__ == "__main__":
    if sys.argv[1:2] == ["--worker"]:
        work(Path(sys.argv[2]),sys.argv[3],sys.argv[4])
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("source",type=Path)
        args = parser.parse_args()
        output = Path(__file__).resolve().parent/"runs"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        output.mkdir(parents=True)
        print(json.dumps(experiment(args.source,output/"log.db"),indent=2))
        print(output)
