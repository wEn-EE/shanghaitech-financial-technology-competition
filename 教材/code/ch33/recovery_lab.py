"""Crash a single writer processing the chapter 32 report log; inspect and restart."""
import multiprocessing as mp
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ch32"))
from window_lab import STARTS, inputs, reference, run


def source_rows(ledger):
    ticks = [(185, 4), (245, 5), (300, 6), (360, 7)]
    history, _, prices = run(inputs(ledger), ticks)
    reports = history + [(86407, s, *reference(prices, s)) for s in STARTS]
    versions = dict.fromkeys(STARTS, 0)
    rows = []
    for offset, (t, window, n, cov) in enumerate(reports):
        versions[window] += 1
        rows.append((offset, window, versions[window], t, n,
                     None if cov is None else str(cov)))
    return rows


def initialize(path, rows):
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript("""
            CREATE TABLE source(i INTEGER PRIMARY KEY, w, v, t, n, cov);
            CREATE TABLE progress(next_i INTEGER NOT NULL);
            INSERT INTO progress VALUES(0);
            CREATE TABLE current(w PRIMARY KEY, v, t, n, cov);
            CREATE TABLE history(w, v, t, n, cov);
        """)
        db.executemany("INSERT INTO source VALUES(?,?,?,?,?,?)", rows)


def apply(db, row, keyed):
    i, w, v, t, n, cov = row
    payload = (w, v, t, n, cov)
    if keyed:
        old = db.execute("SELECT * FROM history WHERE w=? AND v=?", (w, v)).fetchone()
        if old is not None:
            if old != payload:
                raise ValueError("same version with different payload")
            return
    db.execute("INSERT INTO history VALUES(?,?,?,?,?)", payload)
    db.execute("INSERT OR REPLACE INTO current VALUES(?,?,?,?,?)", payload)


def worker(path, mode, fail_at):
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA synchronous=FULL")
        pos = db.execute("SELECT next_i FROM progress").fetchone()[0]
        rows = db.execute("SELECT * FROM source WHERE i>=? ORDER BY i", (pos,)).fetchall()
        for row in rows:
            i = row[0]
            if mode == "early":
                with db:
                    db.execute("UPDATE progress SET next_i=?", (i + 1,))
                if i == fail_at:
                    os._exit(73)
                with db:
                    apply(db, row, False)
            elif mode in ("append", "keyed"):
                with db:
                    apply(db, row, mode == "keyed")
                if i == fail_at:
                    os._exit(73)
                with db:
                    db.execute("UPDATE progress SET next_i=?", (i + 1,))
            else:
                with db:
                    apply(db, row, False)
                    db.execute("UPDATE progress SET next_i=?", (i + 1,))
                    if mode == "before_commit" and i == fail_at:
                        os._exit(73)
                if mode == "after_commit" and i == fail_at:
                    os._exit(73)


def launch(path, mode, fail_at):
    p = mp.get_context("spawn").Process(target=worker, args=(path, mode, fail_at))
    p.start()
    p.join(30)
    if p.is_alive():
        p.terminate()
        p.join()
        raise TimeoutError(mode)
    if p.exitcode != (0 if fail_at is None else 73):
        raise RuntimeError((mode, p.exitcode))


def inspect(path):
    with closing(sqlite3.connect(path)) as db:
        pos = db.execute("SELECT next_i FROM progress").fetchone()[0]
        history = db.execute("SELECT * FROM history ORDER BY rowid").fetchall()
        current = db.execute("SELECT * FROM current ORDER BY w").fetchall()
    return pos, history, current


def experiment(rows, fail_at):
    expected = [row[1:] for row in rows]
    latest = {r[0]: r for r in expected}
    with TemporaryDirectory() as directory:
        for mode in ("early", "append", "keyed", "before_commit", "after_commit"):
            path = Path(directory, mode + ".db")
            initialize(path, rows)
            launch(path, mode, fail_at)
            pos0, hist0, _ = inspect(path)
            launch(path, mode, None)
            pos, history, current = inspect(path)
            print(mode, (pos0, len(hist0)), pos, len(history),
                  current == [latest[k] for k in sorted(latest)], history == expected)
            target = expected.copy()
            if mode == "early":
                target.pop(fail_at)
            if mode == "append":
                target.insert(fail_at, expected[fail_at])
            assert pos == len(rows) and history == target


if __name__ == "__main__":
    reports = source_rows(Path(sys.argv[1]))
    fault = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    if not 0 <= fault < len(reports):
        raise ValueError("fault offset outside source")
    experiment(reports, fault)
