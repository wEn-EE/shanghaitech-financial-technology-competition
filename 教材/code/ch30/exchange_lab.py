"""Trace chapter 29 audit receipts through two logical workers."""
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from opening_lab import indicator, load_quotes, replay, update


OWNER = {"BOND_DEMO": 0, "FX_DEMO": 0, "EQ_DEMO": 1, "GOLD_DEMO": 1}


def read_input(path):
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        receipts = db.execute(
            "SELECT p,o,raw FROM receipt "
            "WHERE g='audit' AND t='market.quotes.ch29.v1' AND status='ACCEPTED'"
        ).fetchall()
    events = []
    for part, offset, raw in receipts:
        q = json.loads(raw)
        if q["event_s"] in (0, 60):
            events.append((q["ready_s"], part, offset, len(raw), q))
    return sorted(events, key=lambda e: e[:3])


def execute(events, route):
    states = [{}, {}]
    counts = [[0, 0], [0, 0]]
    crossing_bytes = 0
    outputs = []
    for arrival, source, offset, size, q in events:
        dest = route(source, q)
        counts[source][dest] += 1
        if dest != source:
            crossing_bytes += size
        update(states[dest], q)
        value = indicator(states[dest], q["asset"])
        if value is not None:
            outputs.append((arrival + 1, q["asset"], value))
    return counts, crossing_bytes, sorted(outputs)


if __name__ == "__main__":
    path = Path(sys.argv[1])
    events = read_input(path)
    reference = sorted(replay(load_quotes(path), "record"))
    plans = {
        "forward": lambda source, q: source,
        "asset": lambda source, q: OWNER[q["asset"]],
        "endpoint": lambda source, q: int(q["event_s"] == 60),
    }
    for name, route in plans.items():
        counts, size, outputs = execute(events, route)
        print(name, counts, size, len(outputs), outputs == reference)
        for t, asset, (start_v, end_v, bp) in outputs:
            print(t, asset, start_v, end_v, f"{float(bp):.6f}")
