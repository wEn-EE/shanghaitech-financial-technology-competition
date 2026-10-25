"""SYNTHETIC teaching lab. Standard library only; no trading connections."""
import hashlib
import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path


def finite(*values):
    if any(isinstance(x, bool) or not isinstance(x, (int, float))
           or not math.isfinite(x) for x in values):
        raise ValueError("finite real numbers required")


def fx_forward(spot, domestic_rate, foreign_rate, years):
    finite(spot, domestic_rate, foreign_rate, years)
    if spot <= 0 or years < 0:
        raise ValueError("positive FX spot and nonnegative tenor required")
    return spot * math.exp((domestic_rate - foreign_rate) * years)


def inverse_quote(bid, ask):
    finite(bid, ask)
    if not 0 < bid <= ask:
        raise ValueError("invalid bid/ask")
    return 1 / ask, 1 / bid


def forward_value(forward, delivery, rate, years, units=1):
    finite(forward, delivery, rate, years, units)
    if years < 0:
        raise ValueError("negative tenor")
    return units * math.exp(-rate * years) * (forward - delivery)


def price_change(previous, current):
    finite(previous, current)
    valid_log = previous > 0 and current > 0
    return {"difference": current - previous,
            "log_return": math.log(current / previous) if valid_log else None,
            "reason": None if valid_log else "NONPOSITIVE_PRICE_LOG_UNDEFINED"}


def roll_ledger(rows, schedule, capital=1000.0, multiplier=10.0,
                fee_per_leg=2.0, schedule_available=0.0):
    """One long contract. Schedule fixed before initial entry; marks equal fills."""
    finite(capital, multiplier, fee_per_leg, schedule_available)
    if capital <= 0 or multiplier <= 0 or fee_per_leg < 0 or not rows:
        raise ValueError("invalid account or empty input")
    if len(rows) != len(schedule):
        raise ValueError("schedule length mismatch")
    if schedule_available > rows[0]["decision_at"]:
        raise ValueError("roll schedule was not known at entry")
    nav, old_contract, old_price, last_time = capital, None, None, -math.inf
    ledger = []
    for row, new_contract in zip(rows, schedule):
        t, available, decision = row["event_at"], row["available_at"], row["decision_at"]
        finite(t, available, decision)
        if not last_time < t <= available <= decision:
            raise ValueError("unordered or unavailable mark")
        needed = {new_contract} | ({old_contract} if old_contract else set())
        if not needed <= row["prices"].keys():
            raise ValueError("missing held/entry contract; no silent fill")
        for contract in needed:
            finite(row["prices"][contract])
        pnl = (0.0 if old_contract is None else
               multiplier * (row["prices"][old_contract] - old_price))
        fee = 2 * fee_per_leg if old_contract and new_contract != old_contract else 0.0
        nav += pnl - fee
        ledger.append({"event_at": t, "available_at": available, "decision_at": decision,
                       "earned_on": old_contract, "held_after": new_contract,
                       "mark_after": row["prices"][new_contract],
                       "variation": pnl, "fee": fee, "equity": nav})
        old_contract, old_price = new_contract, row["prices"][new_contract]
        last_time = t
    return ledger


def margin_stress(equity, old_price, new_price, multiplier, required_margin):
    """One long future; required_margin is supplied, not estimated from price."""
    finite(equity, old_price, new_price, multiplier, required_margin)
    if multiplier <= 0 or required_margin < 0:
        raise ValueError("invalid multiplier or requirement")
    after = equity + multiplier * (new_price - old_price)
    return {"equity_after": after, "cash_shortfall": max(required_margin - after, 0)}


def one_step(spot, strike, up, down, gross):
    finite(spot, strike, up, down, gross)
    if spot <= 0 or strike <= 0 or not 0 < down < gross < up:
        raise ValueError("require positive spot/strike and d < R < u")
    cu, cd = max(spot * up - strike, 0), max(spot * down - strike, 0)
    delta = (cu - cd) / (spot * (up - down))
    cash = (up * cd - down * cu) / ((up - down) * gross)
    probability = (gross - down) / (up - down)
    return {"delta": delta, "cash": cash, "q_probability": probability,
            "call": delta * spot + cash, "up_payoff": cu, "down_payoff": cd}


def option_inputs(spot, strike, rate, sigma, years):
    finite(spot, strike, rate, sigma, years)
    if spot <= 0 or strike <= 0 or sigma <= 0 or years <= 0:
        raise ValueError("BS/CRR require S,K,sigma,T > 0; no boundary extrapolation")


def cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_call(spot, strike, rate, sigma, years):
    option_inputs(spot, strike, rate, sigma, years)
    width = sigma * math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + sigma * sigma / 2) * years) / width
    d2 = d1 - width
    return spot * cdf(d1) - strike * math.exp(-rate * years) * cdf(d2)


def crr_call(spot, strike, rate, sigma, years, steps=200):
    option_inputs(spot, strike, rate, sigma, years)
    if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 2000:
        raise ValueError("steps must be an integer in [1, 2000]")
    dt = years / steps
    up = math.exp(sigma * math.sqrt(dt))
    down, gross = 1 / up, math.exp(rate * dt)
    if not down < gross < up:
        raise ValueError("tree has no interior risk-neutral probability")
    prob = (gross - down) / (up - down)
    values = [max(spot * up ** (2 * j - steps) - strike, 0)
              for j in range(steps + 1)]
    for level in range(steps, 0, -1):
        values = [(prob * values[j + 1] + (1 - prob) * values[j]) / gross
                  for j in range(level)]
    return values[0]


def implied_vol(price, spot, strike, rate, years, low=1e-6, high=3.0):
    finite(price, spot, strike, rate, years, low, high)
    option_inputs(spot, strike, rate, low, years)
    if not low < high:
        raise ValueError("invalid volatility bracket")
    lower = max(spot - strike * math.exp(-rate * years), 0)
    if not lower < price < spot:
        raise ValueError("price not strictly within BS call bounds")
    if not bs_call(spot, strike, rate, low, years) <= price <= bs_call(
            spot, strike, rate, high, years):
        raise ValueError("price outside requested volatility bracket")
    for _ in range(100):
        mid = (low + high) / 2
        value = bs_call(spot, strike, rate, mid, years)
        if abs(value - price) < 1e-10:
            return mid
        if value < price:
            low = mid
        else:
            high = mid
    raise ArithmeticError("IV did not meet price tolerance")


def synthetic_inputs():
    return {"label": "SYNTHETIC", "currency": "DEMO_CCY", "multiplier": 10.0,
            "capital": 1000.0, "fee_per_leg": 2.0, "schedule_available": 0.0,
            "schedule": ["GOLD_DEMO_NEAR", "GOLD_DEMO_FAR",
                         "GOLD_DEMO_FAR", "GOLD_DEMO_FAR"],
            "rows": [{"event_at": float(t), "available_at": t + .05,
                      "decision_at": t + .10,
                      "prices": {"GOLD_DEMO_NEAR": 100.0 + t,
                                 "GOLD_DEMO_FAR": 105.0 + t}}
                     for t in range(4)],
            "fx": {"spot": 7.2, "domestic_rate": .02, "foreign_rate": .05,
                   "years": 1.0, "terminal_spot": 6.8},
            "option": {"spot": 100.0, "strike": 100.0, "rate": .05,
                       "sigma": .20, "years": 1.0},
            "negative_prices": [20.0, -5.0, -2.0]}


def run():
    inputs = synthetic_inputs()
    ledger = roll_ledger(inputs["rows"], inputs["schedule"], inputs["capital"],
                         inputs["multiplier"], inputs["fee_per_leg"],
                         inputs["schedule_available"])
    fx, option = inputs["fx"], inputs["option"]
    forward = fx_forward(**{k: v for k, v in fx.items() if k != "terminal_spot"})
    call = bs_call(**option)
    results = {
        "label": "SYNTHETIC", "ledger": ledger,
        "naive_splice_pnl": [10 * (x["mark_after"] - ledger[0]["mark_after"])
                             for x in ledger],
        "fx_forward": forward,
        "fx_unhedged_return": math.exp(fx["foreign_rate"]) * fx["terminal_spot"] / fx["spot"] - 1,
        "fx_hedged_return": math.exp(fx["foreign_rate"]) * forward / fx["spot"] - 1,
        "margin": margin_stress(100, 100, 88, 10, 80),
        "binomial": one_step(100, 100, 1.2, .8, 1.05),
        "bs_call": call, "bs_put_by_parity": call - 100 + 100 * math.exp(-.05),
        "recovered_iv": implied_vol(call, 100, 100, .05, 1),
        "crr": {str(n): crr_call(**option, steps=n) for n in [25, 50, 100, 200, 400, 401]},
        "negative_price_features": [price_change(a, b) for a, b in
                                    zip(inputs["negative_prices"], inputs["negative_prices"][1:])]}
    root = Path(__file__).resolve().parent / "runs"
    out = root / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True)
    for name, data in [("inputs.json", inputs), ("results.json", results)]:
        (out / name).write_text(json.dumps(data, indent=2, ensure_ascii=False,
                                         allow_nan=False) + "\n", encoding="utf-8")
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {"label": "SYNTHETIC", "python": platform.python_version(),
                "code_sha256": digest(Path(__file__)),
                "files": {p.name: digest(p) for p in sorted(out.glob("*.json"))},
                "assumptions": ["marks equal executable fills by construction",
                                "one long contract, fixed schedule known at entry",
                                "zero collateral interest; roll fees only",
                                "European no-dividend options; constant r and sigma",
                                "toy arrival times, not measured system latency"]}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                      encoding="utf-8")
    print(out)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
