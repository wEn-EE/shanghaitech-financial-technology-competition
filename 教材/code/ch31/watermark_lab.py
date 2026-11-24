"""Replay the chapter 29 synthetic quotes with two logical input streams."""
import sys
from math import inf
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ch30"))
from opening_lab import indicator, load_quotes, update


def schedule(quotes):
    events = []
    for q in quotes:
        gold = q["asset"] == "GOLD_DEMO"
        t = q["ready_s"] + (17 if gold and q["event_s"] == 60 else 0)
        events.append((t, int(gold), q["event_s"], q))
    # Other market traffic advances source time without changing this indicator.
    events.extend([(70, 0, 69, None), (71, 0, 67, None),
                   (91, 0, 90, None), (99, 1, 98, None)])
    return sorted(events, key=lambda x: x[:3])


def replay(events, gap=5, idle=10, grace=20):
    end = 61
    high = [-inf, -inf]
    last = [0, 0]
    water = -inf
    state, reports, side = {}, [], []
    fired = False
    for t, part, event, q in events:
        changed = False
        if q is not None:
            if water >= end + grace:
                side.append((t, q["asset"], q["revision"]))
            else:
                key = q["asset"], event
                old = state.get(key)
                update(state, q)
                changed = state[key] != old

        high[part] = max(high[part], event)
        last[part] = t
        active = [h - gap for h, seen in zip(high, last) if t - seen < idle]
        if active:
            water = max(water, min(active))

        if water >= end and (not fired or changed):
            assets = sorted({asset for asset, _ in state})
            values = [indicator(state, a) for a in assets]
            bp = [v[2] for v in values if v is not None]
            avg = sum(bp) / len(bp) if bp else None
            reports.append((t, water, len(bp), avg))
            fired = True
        if water >= end + grace:
            state.clear()
    return reports, side


def audit(quotes, cutoff):
    state = {}
    for q in quotes:
        if q["ready_s"] <= cutoff:
            update(state, q)
    values = [indicator(state, a) for a in sorted({a for a, _ in state})]
    returns = [v[2] for v in values if v is not None]
    return len(returns), sum(returns) / len(returns) if returns else None


if __name__ == "__main__":
    quotes = load_quotes(Path(sys.argv[1]))
    events = schedule(quotes)
    for idle, grace in [(10, 20), (inf, 20), (10, 0)]:
        reports, side = replay(events, idle=idle, grace=grace)
        print("idle", idle, "grace", grace)
        for t, w, n, mean in reports:
            print(t, w, n, "NA" if mean is None else f"{float(mean):.6f}")
        print("side", side)
    for cutoff in (70, 86405):
        n, mean = audit(quotes, cutoff)
        print("audit", cutoff, n, f"{float(mean):.6f}")
