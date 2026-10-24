"""SYNTHETIC cash-flow lab; not a production security master or trading model."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import platform


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


@dataclass(frozen=True)
class Bond:
    face: float = 100.
    coupon: float = .04
    periods: int = 10
    frequency: int = 2
    elapsed: float = 0.

    def __post_init__(self):
        if not finite(self.face) or self.face <= 0:
            raise ValueError("Positive face required")
        if not finite(self.coupon) or self.coupon < 0:
            raise ValueError("Nonnegative coupon required")
        if type(self.periods) is not int or self.periods < 1:
            raise ValueError("Positive integer periods required")
        if type(self.frequency) is not int or self.frequency < 1:
            raise ValueError("Positive integer frequency required")
        if not finite(self.elapsed) or not 0 <= self.elapsed < 1:
            raise ValueError("Elapsed coupon-period fraction must be in [0,1)")

    def flows(self):
        coupon = self.face * self.coupon / self.frequency
        return [((i - self.elapsed) / self.frequency,
                 coupon + (self.face if i == self.periods else 0))
                for i in range(1, self.periods + 1)]

    def metrics(self, y):
        m = self.frequency
        if not finite(y) or y <= -m:
            raise ValueError("Nominal yield must be finite and greater than -frequency")
        base = 1 + y / m
        pv = [(t, cash * base ** (-m * t)) for t, cash in self.flows()]
        price = sum(v for _, v in pv)
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Numerically invalid price")
        macaulay = sum(t * v for t, v in pv) / price
        modified = macaulay / base
        convexity = sum(t * (t + 1 / m) * v for t, v in pv) / price / base**2
        accrued = self.face * self.coupon / m * self.elapsed
        return {"dirty": price, "clean": price - accrued, "accrued": accrued,
                "macaulay": macaulay, "modified": modified,
                "convexity": convexity, "dv01": price * modified * 1e-4}

    def price(self, y):
        return self.metrics(y)["dirty"]


def solve_ytm(bond, dirty, low=-.5, high=1., tolerance=1e-10):
    if not finite(dirty) or dirty <= 0 or not finite(tolerance) or tolerance <= 0:
        raise ValueError("Positive target price and tolerance required")
    if not finite(low) or not finite(high) or low >= high:
        raise ValueError("Invalid yield bracket")
    pl, ph = bond.price(low), bond.price(high)
    if not ph <= dirty <= pl:
        raise ValueError("Target price is not bracketed; supply a valid range")
    for _ in range(200):
        mid = (low + high) / 2
        price = bond.price(mid)
        if abs(price - dirty) <= tolerance:
            return mid
        if price > dirty:
            low = mid
        else:
            high = mid
    raise RuntimeError("Yield solver did not converge to the price tolerance")


def bootstrap_annual(prices, coupons, face=100.):
    """One annual bond per maturity, integer years, same credit/settlement basis."""
    if len(prices) != len(coupons) or not prices or not finite(face) or face <= 0:
        raise ValueError("Invalid bootstrap inputs")
    discounts = []
    for price, coupon in zip(prices, coupons):
        if not finite(price) or price <= 0 or not finite(coupon) or coupon < 0:
            raise ValueError("Invalid quote")
        d = (price - face * coupon * sum(discounts)) / (face * (1 + coupon))
        if not math.isfinite(d) or d <= 0:
            raise ValueError("Nonpositive discount factor; inspect quotes")
        discounts.append(d)
    return discounts


def curve_price(bond, continuous_zeros):
    flows = bond.flows()
    if len(flows) != len(continuous_zeros) or not all(map(finite, continuous_zeros)):
        raise ValueError("One finite continuous zero rate per payment time required")
    return sum(cash * math.exp(-z * t) for (t, cash), z in zip(flows, continuous_zeros))


def select_action(versions, event_id, as_of):
    if not finite(as_of):
        raise ValueError("Finite as_of required")
    available = [v for v in versions if v["id"] == event_id
                 and max(v["published_at"], v["received_at"]) <= as_of]
    if not available:
        raise LookupError("Corporate-action version unavailable at decision time")
    return max(available, key=lambda v: v["version"])


def stock_return(previous, current, split=1., dividend=0.):
    # dividend is cash/receivable per OLD share; split is new shares per old share.
    if not all(map(finite, (previous, current, split, dividend))):
        raise ValueError("Finite equity inputs required")
    if min(previous, current, split) <= 0 or dividend < 0:
        raise ValueError("Invalid equity prices or corporate-action terms")
    return (split * current + dividend) / previous - 1


def gordon(dividend_next, required, growth):
    if not all(map(finite, (dividend_next, required, growth))):
        raise ValueError("Finite model inputs required")
    if dividend_next < 0 or growth <= -1 or required <= growth:
        raise ValueError("Require nonnegative dividend and required > growth > -1")
    return dividend_next / (required - growth)


def credit_zero(face, risk_free, q_risk_neutral, recovery):
    if not all(map(finite, (face, risk_free, q_risk_neutral, recovery))):
        raise ValueError("Finite credit inputs required")
    if face <= 0 or risk_free <= -1 or not 0 <= q_risk_neutral <= 1 or not 0 <= recovery <= 1:
        raise ValueError("Invalid one-year credit model inputs")
    price = face * (1 - q_risk_neutral * (1 - recovery)) / (1 + risk_free)
    return {"price": price, "promised_yield": face / price - 1 if price > 0 else None,
            "spread": face / price - 1 - risk_free if price > 0 else None}


def main():
    bond, y = Bond(), .03
    base = bond.metrics(y)
    shocks = []
    for bp in (-200, -100, -10, -1, 1, 10, 100, 200):
        dy = bp * 1e-4
        exact = bond.price(y + dy)
        linear = base["dirty"] * (1 - base["modified"] * dy)
        quadratic = linear + base["dirty"] * .5 * base["convexity"] * dy**2
        shocks.append({"shock_bp": bp, "exact": exact, "linear": linear, "quadratic": quadratic})
    # Each revision is a synthetic feed correction, not a real issuer announcement.
    versions = [
        {"id": "DIV1", "version": 1, "effective": 1, "published_at": .2, "received_at": .3, "split": 1., "dividend": 1.},
        {"id": "DIV1", "version": 2, "effective": 1, "published_at": 3.2, "received_at": 3.3, "split": 1., "dividend": 1.2},
        {"id": "SPLIT2", "version": 1, "effective": 2, "published_at": 1.2, "received_at": 1.3, "split": 2., "dividend": 0.}]
    prices = [100., 99., 49.5, 50.]
    index, stock = 100., []
    for t in range(1, len(prices)):
        aid = {1: "DIV1", 2: "SPLIT2"}.get(t)
        action = select_action(versions, aid, t + .1) if aid else {"split": 1., "dividend": 0., "version": None}
        if aid and action["effective"] != t:
            raise ValueError("Action effective date does not match return interval")
        ret = stock_return(prices[t-1], prices[t], action["split"], action["dividend"])
        index *= 1 + ret
        stock.append({"t": t, "available_at": t + .1, "version": action["version"],
                      "raw_return": prices[t] / prices[t-1] - 1,
                      "total_return": ret, "total_index": index})
    corrected = select_action(versions, "DIV1", 3.4)
    revised_first = stock_return(prices[0], prices[1], corrected["split"], corrected["dividend"])
    discounts = bootstrap_annual([100., 100.], [.02, .03])
    zeros = [.03 + .001 * i for i in range(bond.periods)]
    curve_base = curve_price(bond, zeros)
    key_durations = []
    h = 1e-5
    for i in range(len(zeros)):
        up, down = zeros.copy(), zeros.copy()
        up[i] += h
        down[i] -= h
        key_durations.append((curve_price(bond, down)-curve_price(bond, up))/(2*h*curve_base))
    scenarios = []
    for name, d, k, g, by in [("base", 3., .08, .03, .03),
                              ("growth_stress", 2.7, .075, .02, .02),
                              ("discount_stress", 3., .10, .03, .04)]:
        scenarios.append({"name": name, "equity_value": gordon(d, k, g),
                          "bond_price": bond.price(by), "equity_inputs": [d, k, g], "bond_yield": by})
    report = {"source": "SYNTHETIC", "contract": asdict(bond), "base_yield": y,
              "stock_prices": prices, "curve_continuous_zeros": zeros,
              "bootstrap_prices": [100., 100.], "bootstrap_coupons": [.02, .03],
              "bond": base, "ytm_recovered": solve_ytm(bond, base["dirty"]),
              "between_coupons": Bond(elapsed=.5).metrics(y), "shocks": shocks,
              "stock": stock, "action_versions": versions,
              "restated_first_return_as_of_3_4": revised_first,
              "discount_factors": discounts, "two_year_spot": discounts[1]**(-.5)-1,
              "forward_year_1_to_2": discounts[0]/discounts[1]-1,
              "curve_price": curve_base, "cashflow_node_durations": key_durations,
              "credit": credit_zero(100., .03, .02, .4), "scenarios": scenarios}
    out = Path(__file__).parent / "runs" / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True, exist_ok=False)
    target = out / "results.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    manifest = {"python": platform.python_version(), "source": "SYNTHETIC",
                "convention": "nominal annual YTM, semiannual, equal coupon periods; no calendar",
                "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), target]}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(out.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
