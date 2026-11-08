"""Causal feature lab: synthetic equal-step bars, standard library only."""
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean, median, pstdev, stdev
import hashlib
import json
import math
import platform
import random

ASSETS = ("EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO")
NAMES = ("ret1", "mom5", "vol5", "ema_gap", "spread_bps", "impact5")
WINDOW, ALPHA, TRAIN_END, MODEL_READY = 5, 0.3, 40, 41


def valid_price(x):
    return x is not None and math.isfinite(x) and x > 0


class Engine:
    def __init__(self):
        self.last = -1
        self.rows = deque(maxlen=WINDOW + 1)
        self.ema = None
        self.ema_start = None

    def step(self, b):
        if b["t"] != self.last + 1 or b["ready"] != b["t"] + 1:
            raise ValueError("expected consecutive finalized synthetic bars")
        p = b["price"]
        if p is not None and not valid_price(p):
            raise ValueError("invalid price; upstream quarantine required")
        if not math.isfinite(b["notional"]) or b["notional"] < 0:
            raise ValueError("invalid notional")
        if p is not None and not (math.isfinite(b["bid"]) and math.isfinite(b["ask"])
                                  and 0 < b["bid"] <= b["ask"]):
            raise ValueError("invalid quote")
        self.last = b["t"]
        self.rows.append(dict(b))
        if p is None:
            self.ema_start = None
        elif self.ema is None:
            self.ema_start = b["id"]
        self.ema = (None if p is None else p if self.ema is None
                    else (1 - ALPHA) * self.ema + ALPHA * p)
        rows = list(self.rows)
        x = dict.fromkeys(NAMES)
        if p is not None:
            mid = (b["bid"] + b["ask"]) / 2
            x["spread_bps"] = 10000 * (b["ask"] - b["bid"]) / mid
            x["ema_gap"] = p / self.ema - 1
        if len(rows) >= 2 and all(valid_price(r["price"]) for r in rows[-2:]):
            x["ret1"] = rows[-1]["price"] / rows[-2]["price"] - 1
        if len(rows) == WINDOW + 1 and all(valid_price(r["price"]) for r in rows):
            returns = [rows[i]["price"] / rows[i-1]["price"] - 1
                       for i in range(1, len(rows))]
            x["mom5"] = rows[-1]["price"] / rows[0]["price"] - 1
            x["vol5"] = stdev(returns)
            notionals = [r["notional"] for r in rows[1:]]
            if all(v > 0 for v in notionals):
                x["impact5"] = fmean(abs(r) / v for r, v in zip(returns, notionals))
        return {"asset": b["asset"], "t": b["t"], "ready": b["ready"],
                "x": x, "window_ids": [r["id"] for r in rows],
                "ema_start_id": self.ema_start}


def panel(bars):
    engines = {a: Engine() for a in ASSETS}
    return [engines[b["asset"]].step(b) for b in bars]


def quantile(values, q):
    s = sorted(values)
    h = (len(s) - 1) * q
    lo, hi = math.floor(h), math.ceil(h)
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def fit(rows, kind="standard"):
    if kind not in ("standard", "robust"):
        raise ValueError("unknown scaler")
    if any(r["ready"] > TRAIN_END for r in rows):
        raise ValueError("future row in training")
    if not rows:
        raise ValueError("empty training")
    params = {}
    for a in ASSETS:
        usable = [r for r in rows if r["asset"] == a
                  and all(r["x"][k] is not None for k in NAMES)]
        if len(usable) < 2:
            raise ValueError("insufficient complete training rows")
        params[a] = {}
        for k in NAMES:
            values = [r["x"][k] for r in usable]
            center = fmean(values) if kind == "standard" else median(values)
            scale = (pstdev(values) if kind == "standard"
                     else quantile(values, 0.75) - quantile(values, 0.25))
            params[a][k] = {"center": center, "scale": scale or 1.0,
                           "constant": scale == 0, "n": len(values)}
    return {"kind": kind, "ready": MODEL_READY, "train_end": TRAIN_END,
            "params": params}


def transform(row, scaler):
    if row["ready"] < scaler["ready"]:
        raise ValueError("scaler not ready for this historical decision")
    z, clipped, flags = {}, {}, {}
    for k, value in row["x"].items():
        p = scaler["params"][row["asset"]][k]
        z[k] = None if value is None else (value - p["center"]) / p["scale"]
        clipped[k] = None if z[k] is None else max(-4.0, min(4.0, z[k]))
        flags[k] = z[k] is not None and abs(z[k]) > 4
    return {**row, "z": z, "clipped_z": clipped, "clipped": flags,
            "scaler_kind": scaler["kind"]}


def macro_inputs():
    releases = [
        {"id": "sep-v1", "period": "2026-09", "rev": 1,
         "pub": 45, "ready": 46, "value": 2.3},
        {"id": "sep-v2", "period": "2026-09", "rev": 2,
         "pub": 65, "ready": 66, "value": 2.7},
        {"id": "oct-v1", "period": "2026-10", "rev": 1,
         "pub": 80, "ready": 81, "value": 2.4},
    ]
    forecasts = [
        {"id": "sep-pre", "period": "2026-09", "ready": 44, "value": 2.1},
        {"id": "sep-late", "period": "2026-09", "ready": 46, "value": 2.25},
        {"id": "oct-pre", "period": "2026-10", "ready": 79, "value": 2.5},
    ]
    return releases, forecasts


def macro_at(cut, releases, forecasts):
    visible = [r for r in releases if r["ready"] <= cut]
    if not visible:
        return None
    period = max(r["period"] for r in visible)
    current = max((r for r in visible if r["period"] == period),
                  key=lambda r: r["rev"])
    first = next((r for r in visible if r["period"] == period and r["rev"] == 1),
                 None)
    pre = ([] if first is None else
           [f for f in forecasts if f["period"] == period
            and f["ready"] < first["pub"]])
    forecast = max(pre, key=lambda f: f["ready"]) if pre else None
    surprise = None if forecast is None else first["value"] - forecast["value"]
    age = None if first is None else cut - first["ready"]
    return {"period": period, "level": current["value"], "id": current["id"],
            "first_id": None if first is None else first["id"],
            "forecast_id": None if forecast is None else forecast["id"],
            "surprise_pp": surprise,
            "revision_pp": None if first is None else current["value"] - first["value"],
            "first_age": age,
            "decayed_surprise": None if surprise is None else surprise * 2 ** (-age / 10)}


def samples(n=96):
    rng = random.Random(20261108)
    prices = dict(zip(ASSETS, (100.0, 99.0, 2000.0, 7.0)))
    bars = []
    for t in range(n):
        for j, a in enumerate(ASSETS):
            r = 0.0003 * (j + 1) + rng.gauss(0, 0.001 * (j + 1))
            if a == "EQ_DEMO" and t == 72:
                r = -0.08
            prices[a] *= 1 + r
            p = None if a == "EQ_DEMO" and t == 55 else prices[a]
            spread = 2 + j + (t % 5) * 0.2
            bars.append({
                "id": f"{a}-{t}", "asset": a, "t": t, "ready": t + 1, "price": p,
                "bid": None if p is None else p * (1 - spread / 20000),
                "ask": None if p is None else p * (1 + spread / 20000),
                "notional": 0.0 if a == "FX_DEMO" and t == 60
                            else 1e6 * (j + 1) * (1 + (t % 7) / 10)
            })
    return bars


def run():
    bars = samples()
    raw = panel(bars)
    training = [r for r in raw if r["ready"] <= TRAIN_END]
    standard, robust = fit(training), fit(training, "robust")
    online = [transform(r, standard) for r in raw if r["ready"] >= MODEL_READY]
    releases, forecasts = macro_inputs()
    return {
        "data_kind": "SYNTHETIC", "seed": 20261108,
        "clock": "equal steps; bar t available at t+1; zero feature latency",
        "contract": {"window": WINDOW, "alpha": ALPHA, "ddof_vol": 1,
                     "ddof_scaler": 0, "clip": 4, "ema_gap_policy": "reset",
                     "notional_unit": "common synthetic currency"},
        "bars": bars, "raw_features": raw,
        "scalers": {"standard": standard, "robust": robust},
        "online": online, "macro_inputs": [releases, forecasts],
        "macro": {str(t): macro_at(t, releases, forecasts)
                  for t in (45, 46, 56, 66, 81)}
    }


def main():
    result = run()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = Path(__file__).parent / "runs" / ("run_" + stamp)
    out.mkdir(parents=True)
    p = out / "results.json"
    p.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
                 encoding="utf-8")
    manifest = {
        "python": platform.python_version(),
        "program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "results_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "bars": len(result["bars"]), "online_rows": len(result["online"]),
        "clipped_rows": sum(any(r["clipped"].values()) for r in result["online"])
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"run_dir": str(out), **manifest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
