"""Replay two three-minute covariance windows on a logical clock."""
from fractions import Fraction as F
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ch30"))
from opening_lab import load_quotes

ASSETS = ("EQ_DEMO", "GOLD_DEMO")
STARTS = (1, 2)


def inputs(path):
    rows, base = [], {}
    for q in load_quotes(path):
        a = q["asset"]
        if a not in ASSETS:
            continue
        m = q["event_s"] // 60
        p = F(q["price_atoms"], 10 ** q["scale"])
        t = q["ready_s"] + (17 if a == ASSETS[1] and m == 1 else 0)
        rows.append((t, a, m, q["revision"], p))
        if m == 1 and q["revision"] == 1:
            base[a] = p
    for a, changes in zip(ASSETS, [(2, -1, 3), (1, 2, -2)]):
        p = base[a]
        for m, bp in enumerate(changes, start=2):
            p *= 1 + F(bp, 10000)
            t = 190 if a == ASSETS[1] and m == 2 else 60 * m + 1
            rows.append((t, a, m, 1, p))
    return sorted(rows)


def pair(prices, m):
    values = []
    for a in ASSETS:
        if (a, m - 1) not in prices or (a, m) not in prices:
            return None
        p0 = prices[a, m - 1][1]
        p1 = prices[a, m][1]
        values.append(10000 * (p1 / p0 - 1))
    return tuple(values)


class Window:
    def __init__(self):
        self.pairs = {}
        self.sx = self.sy = self.sxy = F(0)

    def replace(self, m, value):
        if value is None or self.pairs.get(m) == value:
            return
        x, y = self.pairs.get(m, (0, 0))
        u, v = value
        self.sx += u - x
        self.sy += v - y
        self.sxy += u * v - x * y
        self.pairs[m] = value

    def result(self):
        n = len(self.pairs)
        cov = (self.sxy - self.sx * self.sy / n) / (n - 1) if n >= 2 else None
        return n, cov


def run(rows, ticks, grace=2):
    prices, side, history = {}, [], []
    windows = {s: Window() for s in STARTS}
    previous = {}
    water = 0
    timeline = [(r[0], 0, r) for r in rows] + [(t, 1, w) for t, w in ticks]
    for t, kind, item in sorted(timeline):
        if kind == 1:
            water = max(water, item)
        else:
            _, a, m, rev, p = item
            old = prices.get((a, m))
            if old is not None and rev == old[0] and p != old[1]:
                raise ValueError("conflicting quote version")
            if old is not None and rev <= old[0]:
                continue
            prices[a, m] = rev, p
            for k in (m, m + 1):
                for s in STARTS:
                    if s <= k < s + 3:
                        if s in windows:
                            windows[s].replace(k, pair(prices, k))
                        else:
                            side.append((t, s, k))
        for s in list(windows):
            end = s + 3
            if water >= end:
                result = windows[s].result()
                if previous.get(s) != result:
                    history.append((t, s, *result))
                    previous[s] = result
            if water >= end + grace:
                del windows[s]
    return history, side, prices


def reference(prices, start):
    pairs = [pair(prices, m) for m in range(start, start + 3)]
    xy = [v for v in pairs if v is not None]
    n = len(xy)
    if n < 2:
        return n, None
    mx, my = (sum(col) / n for col in zip(*xy))
    return n, sum((x - mx) * (y - my) for x, y in xy) / (n - 1)


if __name__ == "__main__":
    rows = inputs(Path(sys.argv[1]))
    ticks = [(185, 4), (245, 5), (300, 6), (360, 7)]
    history, side, prices = run(rows, ticks)
    for t, start, n, cov in history:
        print(t, start, n, "NA" if cov is None else f"{float(cov):.6f}")
    print("late", side)
    for start in STARTS:
        n, cov = reference(prices, start)
        print("audit", start, n, f"{float(cov):.6f}")
