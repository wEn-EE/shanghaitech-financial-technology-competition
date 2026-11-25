"""Chapter 31: test watermark decisions against untouched input and publication history."""
import sqlite3
import sys
from contextlib import closing
from fractions import Fraction
from pathlib import Path

from watermark_lab import audit, load_quotes, replay, schedule


def drawdowns(events):
    high = None
    distances = []
    for event in events:
        if high is not None:
            distances.append(max(high - event, 0))
        high = event if high is None else max(high, event)
    return distances


def screen(events, lead):
    accepted, quarantine = [], []
    for row in events:
        t, part, event, _ = row
        if event > t + lead:
            quarantine.append((t, part, event))
        else:
            accepted.append(row)
    return accepted, quarantine


def publish(db, version, visible, n, bp):
    record = (version, visible, n, str(bp))
    with db:
        prior = db.execute("SELECT * FROM report WHERE version=?", (version,)).fetchone()
        if prior is None:
            db.execute("INSERT INTO report VALUES (?,?,?,?)", record)
        elif prior != record:
            raise ValueError("publication conflict")


def asof(db, t):
    return db.execute(
        "SELECT version, covered, value FROM report WHERE visible<=? "
        "ORDER BY visible DESC, version DESC LIMIT 1", (t,)
    ).fetchone()


def main(path):
    train = drawdowns([10, 14, 13, 20, 16, 21, 19, 25, 20, 30, 27])
    holdout = drawdowns([40, 46, 40, 49, 44, 53, 45, 58, 54, 61, 54])
    for gap in (2, 5, 8):
        print("gap", gap, sum(d > gap for d in train), sum(d > gap for d in holdout))

    quotes = load_quotes(path)
    events = schedule(quotes)
    polluted = sorted(events + [(68, 0, 3600, None)], key=lambda row: row[:3])
    kept, rejected = screen(polluted, lead=2)
    for label, data in [("raw", polluted), ("screened", kept)]:
        reports, side = replay(data)
        print(label, [(t, w, n) for t, w, n, mean in reports], side)
    print("quarantine", rejected)
    assert kept == events

    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE report(version INTEGER PRIMARY KEY, visible INTEGER, "
                   "covered INTEGER, value TEXT)")
        reports, _ = replay(kept)
        for version, (t, _, n, value) in enumerate(reports, start=1):
            publish(db, version, t, n, value)
            publish(db, version, t, n, value)
        n, value = audit(quotes, 86405)
        publish(db, 3, 86407, n, value)
        try:
            publish(db, 2, 78, 4, Fraction(0))
        except ValueError as exc:
            print(exc)
        for t in (69, 70, 77, 78, 86405, 86407):
            row = asof(db, t)
            print(t, (row[0], row[1], round(float(Fraction(row[2])), 6)) if row else None)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
