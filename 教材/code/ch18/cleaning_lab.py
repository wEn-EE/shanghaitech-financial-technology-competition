"""SYNTHETIC causal cleaning lab. Python standard library only."""
import copy
import hashlib
import json
import math
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

UNITS = {"EQ_DEMO": "CNY/share", "BOND_DEMO": "percent_of_par_clean",
         "GOLD_DEMO": "USD/troy_ounce", "FX_DEMO": "CNY/USD"}
CONFIG = dict(window=8, minimum=6, threshold=3.5, floor=0.00001, max_age=2)


def encode(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, allow_nan=False)


def clean(rows, config=None):
    cfg = dict(CONFIG if config is None else config)
    if not (0 < cfg["minimum"] <= cfg["window"] and cfg["floor"] > 0
            and cfg["threshold"] > 0 and cfg["max_age"] >= 0):
        raise ValueError("Invalid configuration")
    seen, states, outputs, audit = {}, {}, [], []
    for receipt_id, row in enumerate(rows, 1):
        raw = encode(row)  # Teaching input is already decoded JSON.
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        log = dict(receipt_id=receipt_id, input_sha256=digest)
        def reject(reason):
            audit.append(dict(log, action="QUARANTINE", reason=reason))
        if set(row) != {"asset", "t", "available", "unit", "price"}:
            reject("SCHEMA"); continue
        asset, t, available, price = (row[k] for k in ("asset", "t", "available", "price"))
        if asset not in UNITS or type(t) is not int or type(available) is not int or available < t:
            reject("IDENTITY_OR_TIME"); continue
        key = (asset, t)
        if key in seen:
            if seen[key] == raw:
                audit.append(dict(log, action="DUPLICATE", reason="SAME_CONTENT"))
            else:
                reject("SAME_KEY_CONFLICT")
            continue
        if row["unit"] != UNITS[asset]:
            reject("UNIT"); continue
        if price is not None and (type(price) not in (float, int)
                                  or not math.isfinite(price) or price <= 0):
            reject("PRICE"); continue
        state = states.setdefault(asset, dict(t=-1, available=-1, last=None,
                                              history=deque(maxlen=cfg["window"])))
        if t <= state["t"] or available < state["available"]:
            reject("ORDER_REQUIRES_REPLAY"); continue
        seen[key] = raw
        last = state["last"]
        age = None if last is None else t-last[0]
        ret = score = None
        if price is None:
            view = last[1] if last and age <= cfg["max_age"] else None
            status = "IMPUTED" if view is not None else "MISSING"
            reason = "BOUNDED_FORWARD_FILL" if view is not None else "NO_FRESH_ANCHOR"
        else:
            view, status, reason = price, "OBSERVED", "VALID_DOMAIN"
            # A missing or quarantined grid point breaks the one-step return.
            if last and last[0] == t-1:
                ret = math.log(price)-math.log(last[1])
                history = state["history"]
                if len(history) >= cfg["minimum"]:
                    center = median(history)
                    mad = median(abs(x-center) for x in history)
                    scale = max(mad/0.6744897501960817, cfg["floor"])
                    score = (ret-center)/scale
                    if abs(score) > cfg["threshold"]:
                        status, reason = "FLAGGED", "ROBUST_RETURN_SCORE"
                else:
                    reason = "WARMUP"
                history.append(ret)  # Score first; update afterwards, including flagged values.
            state["last"] = (t, price)
            age = 0
        outputs.append(dict(asset=asset, t=t, available=available, raw_price=price,
                            view_price=view, age=age, status=status, log_return=ret,
                            score=score, source_receipt=receipt_id))
        audit.append(dict(log, action=status, reason=reason))
        state["t"], state["available"] = t, available
    return dict(config=cfg, output=outputs, audit=audit,
                counts=dict(Counter(x["action"] for x in audit)))


def samples():
    rows = []
    for asset, initial in zip(UNITS, (100.0, 99.0, 2000.0, 7.0)):
        price = initial
        for t in range(24):
            price *= math.exp((0.001, -0.001, 0.0005, -0.0005)[t % 4])
            if asset == "EQ_DEMO" and t == 16:
                price *= 0.92  # Genuine synthetic market jump, retained.
            value = None if asset == "EQ_DEMO" and t in (9, 10, 11) else price
            row = dict(asset=asset, t=t, available=t, unit=UNITS[asset], price=value)
            if asset == "BOND_DEMO" and t == 12:
                row["unit"] = "CNY"
            if asset == "GOLD_DEMO" and t == 12:
                row["price"] = -1
            rows.append(row)
    rows.sort(key=lambda r: (r["available"], r["asset"]))
    rows.insert(5, copy.deepcopy(rows[4]))
    conflict = copy.deepcopy(rows[0]); conflict["price"] *= 1.1
    rows.append(conflict)
    return rows


def main():
    root = Path(__file__).parent
    out = root/"runs"/datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True)
    rows = samples()
    result = clean(rows)
    (out/"inputs.json").write_text(encode(rows)+"\n", encoding="utf-8")
    (out/"results.json").write_text(encode(result)+"\n", encoding="utf-8")
    manifest = dict(data_kind="SYNTHETIC", policy_version="ch18-v1",
                    time_unit="abstract grid step; zero processing delay assumed",
                    hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in (Path(__file__), out/"inputs.json", out/"results.json")})
    (out/"manifest.json").write_text(encode(manifest)+"\n", encoding="utf-8")
    print(result["counts"])
    print("output rows:", len(result["output"]), "receipts:", len(rows))
    print(out.resolve())


if __name__ == "__main__":
    main()
