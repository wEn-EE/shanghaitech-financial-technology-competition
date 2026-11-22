"""Replay chapter 29's validated opening quotes on a logical clock."""
import json
import sqlite3
import sys
from contextlib import closing
from fractions import Fraction
from itertools import groupby
from pathlib import Path


def load_quotes(path):
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        rows = db.execute(
            "SELECT body FROM event WHERE g='audit' AND s IN (0,60)"
        ).fetchall()
    if not rows:
        raise ValueError("missing chapter 29 audit events")
    return sorted((json.loads(body) for body, in rows),
                  key=lambda q: (q["ready_s"], q["asset"], q["revision"]))


def update(state, quote):
    key = (quote["asset"], quote["event_s"])
    old = state.get(key)
    if old is None or quote["revision"] > old["revision"]:
        state[key] = quote


def indicator(state, asset):
    first = state.get((asset, 0))
    last = state.get((asset, 60))
    if first is None or last is None:
        return None
    def price(q):
        return Fraction(q["price_atoms"], 10 ** q["scale"])
    return (first["revision"], last["revision"],
            10000 * (price(last) / price(first) - 1))


def replay(quotes, mode, period=10):
    def trigger(q):
        arrival = q["ready_s"]
        if mode == "record":
            return arrival
        if mode == "micro":
            return ((arrival + period - 1) // period) * period
        raise ValueError(mode)

    state = {}
    if mode == "batch":
        for cut in (120, 86520):
            state = {}
            for q in quotes:
                if q["ready_s"] <= cut:
                    update(state, q)
            for asset in sorted({asset for asset, _ in state}):
                result = indicator(state, asset)
                if result is not None:
                    yield cut + 1, asset, result
        return

    for cut, group in groupby(quotes, trigger):
        touched = set()
        for q in group:
            asset = q["asset"]
            update(state, q)
            if mode == "record":
                result = indicator(state, asset)
                if result is not None:
                    yield cut + 1, asset, result
            touched.add(asset)
        if mode == "micro":
            for asset in sorted(touched):
                result = indicator(state, asset)
                if result is not None:
                    yield cut + 1, asset, result


if __name__ == "__main__":
    quotes = load_quotes(Path(sys.argv[1]))
    for mode in ("batch", "micro", "record"):
        for visible, asset, (v0, v60, bp) in replay(quotes, mode):
            print(mode, visible, asset, v0, v60, f"{float(bp):.6f}")
