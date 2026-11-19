"""Synthetic quotes: SQLite point-in-time reads and a versioned Parquet export."""
import argparse
import hashlib
import json
import sqlite3
from decimal import Decimal
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

DAY = 86400
FIELDS = ("asset", "event_s", "revision", "ready_s", "price_atoms", "scale", "seed_uid")
SCHEMA = """
CREATE TABLE quotes (
 asset TEXT NOT NULL, event_s INTEGER NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
 ready_s INTEGER NOT NULL CHECK(ready_s>=event_s), price_atoms INTEGER NOT NULL,
 scale INTEGER NOT NULL, seed_uid TEXT NOT NULL, PRIMARY KEY(asset,event_s,revision)
) STRICT;
"""
LATEST = """SELECT event_s,revision,price_atoms FROM quotes
WHERE asset=? AND event_s<=? AND ready_s<=?
ORDER BY event_s DESC, revision DESC LIMIT 1"""
AUDIT_FIELDS = ("asset","event_s","revision","price_atoms","scale","seed_uid","ready_s")
WINDOW = """SELECT asset,event_s,revision,price_atoms,scale,seed_uid,ready_s FROM (
 SELECT *,row_number() OVER (
 PARTITION BY asset,event_s ORDER BY revision DESC) AS pos
 FROM quotes WHERE event_s>=? AND event_s<? AND ready_s<=?
) WHERE pos=1 ORDER BY asset,event_s"""
RANGE = "SELECT event_s,asset,price_atoms FROM quotes WHERE event_s>=? AND event_s<? ORDER BY event_s,asset"


def seeds(path):
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True)) as db:
        records = db.execute("""SELECT instrument_id,price_atoms,price_scale,event_uid
          FROM quote JOIN instrument USING(instrument_id) ORDER BY instrument_id""").fetchall()
    if len(records) != 4 or {r[0] for r in records} != {"EQ_DEMO","BOND_DEMO","GOLD_DEMO","FX_DEMO"}:
        raise ValueError("expected four seed quotes from chapter 26")
    return records


def load(db, records):
    db.executescript(SCHEMA)
    rows = []
    for asset, price, scale, uid in records:
        for day in range(3):
            for minute in range(60):
                t = day * DAY + minute * 60
                rows.append((asset, t, 1, t+1, price+minute, scale, uid))
        if asset == "EQ_DEMO":
            rows.append((asset, 60, 2, DAY+5, price+41, scale, uid))
    with db:
        db.executemany("INSERT INTO quotes VALUES (?,?,?,?,?,?,?)", rows)


def archive(db, directory):
    # Offline snapshot: one writer, no mutations during the export transaction.
    parts = []
    db.execute("BEGIN")
    try:
        for (day,) in db.execute("SELECT DISTINCT event_s / ? FROM quotes ORDER BY 1", (DAY,)):
            start = day * DAY
            rows = db.execute("SELECT * FROM quotes WHERE event_s>=? AND event_s<? "
                              "ORDER BY event_s,asset,revision", (start,start+DAY))
            table = pa.Table.from_pylist([dict(zip(FIELDS,row)) for row in rows])
            path = directory / f"day-{day}.parquet"
            pq.write_table(table, path, row_group_size=64)
            parts.append(dict(file=path.name, start=start, stop=start+DAY,
                              rows=table.num_rows, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    finally:
        db.rollback()  # ends the read snapshot
    temp = directory / "manifest.tmp"
    temp.write_text(json.dumps(parts, indent=2), encoding="utf-8")
    temp.replace(directory / "manifest.json")


def cold_window(directory, lo, hi, cutoff):
    parts = json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
    chosen, latest = [], {}
    for part in parts:
        if part["stop"] <= lo or part["start"] >= hi:
            continue
        path = directory / part["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != part["sha256"]:
            raise ValueError("archive checksum mismatch")
        chosen.append(path.name)
        table = pq.read_table(path, columns=list(AUDIT_FIELDS))
        for row in table.to_pylist():
            t, rev = row["event_s"], row["revision"]
            if lo <= t < hi and row["ready_s"] <= cutoff:
                key = (row["asset"], t)
                if key not in latest or latest[key][0] < rev:
                    latest[key] = tuple(row[name] for name in AUDIT_FIELDS[2:])
    return [(*key,*latest[key]) for key in sorted(latest)], chosen


def compare(db, directory, lo, hi, cutoff):
    hot = db.execute(WINDOW, (lo,hi,cutoff)).fetchall()
    cold, selected = cold_window(directory, lo, hi, cutoff)
    if len(hot) != len(cold):
        raise AssertionError(f"row count: hot={len(hot)}, cold={len(cold)}")
    for left, right in zip(hot, cold):
        for name, a, b in zip(AUDIT_FIELDS, left, right):
            if a != b:
                prices = [Decimal(r[3]).scaleb(-r[4]) for r in (left, right)]
                raise AssertionError(f"{left[:3]} {name}: hot={a}, cold={b}; "
                                     f"price hot={prices[0]}, cold={prices[1]}")
    return dict(rows=len(hot), files=selected, equity=[r[:4] for r in hot if r[:2]==("EQ_DEMO",60)])


def equity_feature(db, cutoff):
    panel = db.execute(WINDOW, (0,120,cutoff)).fetchall()
    pair = [r for r in panel if r[0] == "EQ_DEMO"]
    if len(pair) != 2:
        return dict(status="MISSING_INPUT", cutoff=cutoff)
    earlier, later = pair
    previous_price, current_price = (Decimal(row[3]).scaleb(-row[4]) for row in pair)
    if previous_price == 0:
        return dict(status="ZERO_BASE_PRICE", cutoff=cutoff)
    return dict(status="OK", name="first_minute_return.v1", cutoff=cutoff,
                inputs=[r[:3] for r in pair], value=float(current_price/previous_price-1))


def run(source, directory):
    records = seeds(source)
    directory.mkdir(parents=True, exist_ok=False)
    with closing(sqlite3.connect(directory/"hot.db")) as db:
        load(db, records)
        with db:
            db.execute("CREATE TABLE import_source(path TEXT PRIMARY KEY NOT NULL)")
            db.execute("INSERT INTO import_source VALUES (?)", (str(source.resolve()),))
        bounds = (DAY, DAY+120)
        before = db.execute(RANGE, bounds).fetchall()
        def plan():
            return [row[3] for row in db.execute("EXPLAIN QUERY PLAN "+RANGE, bounds)]
        old_plan = plan()
        db.execute("CREATE INDEX by_time ON quotes(event_s,asset,price_atoms)")
        if before != db.execute(RANGE, bounds).fetchall():
            raise AssertionError("index changed result")
        archive(db, directory)
        return dict(data="SYNTHETIC", physical_rows=db.execute("SELECT count(*) FROM quotes").fetchone()[0],
                    before=old_plan, after=plan(), range_rows=len(before),
                    decision=compare(db,directory,0,120,120),
                    revised=compare(db,directory,0,120,DAY+5),
                    feature=[equity_feature(db,t) for t in (120,DAY+5)],
                    latest=db.execute(LATEST,("EQ_DEMO",DAY+5,DAY+5)).fetchone())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    run_dir = Path(__file__).resolve().parent / "runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    print(json.dumps(run(args.source, run_dir), indent=2))
    print(run_dir)
