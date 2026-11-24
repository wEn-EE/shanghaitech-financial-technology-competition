"""Score the five versioned results in the chapter 30 fixture on a logical clock."""
import sys
from fractions import Fraction
from pathlib import Path

from opening_lab import load_quotes, replay


def expected_versions(quotes):
    # The fixture has exactly one opening version per asset.
    opening = {q["asset"]: q for q in quotes if q["event_s"] == 0}
    assert len(opening) == 4 and sum(q["event_s"] == 0 for q in quotes) == 4
    expected = {}
    for close in quotes:
        if close["event_s"] != 60:
            continue
        asset = close["asset"]
        start = opening[asset]
        ratio = Fraction(close["price_atoms"] * 10 ** start["scale"],
                         start["price_atoms"] * 10 ** close["scale"])
        key = asset, start["revision"], close["revision"]
        assert key not in expected
        expected[key] = max(start["ready_s"], close["ready_s"]), 10000 * (ratio - 1)
    assert len(expected) == 5
    return expected


def delays(outputs, expected):
    first = {}
    for visible, asset, (v0, v60, value) in outputs:
        key = asset, v0, v60
        ready, target = expected[key]
        assert visible >= ready and value == target
        first[key] = min(visible, first.get(key, visible))
    assert first.keys() == expected.keys()
    return sorted(first[k] - expected[k][0] for k in first)


if __name__ == "__main__":
    quotes = load_quotes(Path(sys.argv[1]))
    expected = expected_versions(quotes)
    for mode, period in [("batch", 0), ("micro", 10), ("micro", 4), ("record", 0)]:
        lag = delays(replay(quotes, mode, period), expected)
        print(mode, period, lag, sum(d <= 5 for d in lag), "/", len(lag))
