"""SYNTHETIC continuous order book and sequenced feed, standard library only."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import platform

ASSETS = ("EQ_DEMO", "BOND_DEMO", "GOLD_DEMO", "FX_DEMO")


def positive_int(value):
    return type(value) is int and value > 0


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Book:
    def __init__(self):
        self.orders = {}
        self.used_ids = set()
        self.trades = []

    def levels(self, side):
        totals = {}
        for order in self.orders.values():
            if order["side"] == side:
                price = order["price"]
                totals[price] = totals.get(price, 0) + order["qty"]
        return sorted(totals.items(), reverse=(side == "B"))

    def quote(self):
        bids, asks = self.levels("B"), self.levels("S")
        if not bids or not asks:
            return {"status": "EMPTY" if not bids and not asks else "ONE_SIDED", "bid": bids[0][0] if bids else None,
                    "ask": asks[0][0] if asks else None, "mid": None,
                    "spread_bps": None, "imbalance": None}
        bid, qb = bids[0]
        ask, qa = asks[0]
        assert bid < ask
        mid = (bid + ask) / 2
        return {"status": "TWO_SIDED", "bid": bid, "ask": ask, "mid": mid,
                "spread_bps": (ask - bid) / mid * 10000,
                "imbalance": (qb - qa) / (qb + qa)}

    def apply(self, event):
        action, oid, qty = event.get("action"), event.get("order_id"), event.get("qty")
        if not isinstance(oid, str) or not oid or not positive_int(qty):
            raise ValueError("Invalid order ID or positive integer quantity")
        if action == "CANCEL":
            if oid not in self.orders or qty > self.orders[oid]["qty"]:
                raise ValueError("Unknown order or cancellation exceeds remaining quantity")
            self.orders[oid]["qty"] -= qty
            if self.orders[oid]["qty"] == 0:
                del self.orders[oid]
            return {"action": action, "cancelled": qty, "trades": []}
        side, kind, price = event.get("side"), event.get("kind"), event.get("price")
        if action != "NEW" or side not in ("B", "S") or kind not in ("LMT", "MKT"):
            raise ValueError("Unsupported order type")
        if oid in self.used_ids:
            raise ValueError("Order ID cannot be reused")
        if (kind == "LMT" and not positive_int(price)) or (kind == "MKT" and price is not None):
            raise ValueError("Limit price must be integer ticks; market price must be null")
        # Validate before mutating the book.
        self.used_ids.add(oid)
        opposite = [o for o in self.orders.values() if o["side"] != side]
        opposite.sort(key=lambda o: (o["price"] if side == "B" else -o["price"], o["seq"]))
        remaining, fills = qty, []
        for maker in opposite:
            if not remaining:
                break
            crosses = kind == "MKT" or (price >= maker["price"] if side == "B" else price <= maker["price"])
            if not crosses:
                break
            amount = min(remaining, maker["qty"])
            fill = {"seq": event["seq"], "maker": maker["order_id"], "taker": oid,
                    "side": side, "price": maker["price"], "qty": amount}
            fills.append(fill)
            maker["qty"] -= amount
            remaining -= amount
            if maker["qty"] == 0:
                del self.orders[maker["order_id"]]
        self.trades.extend(fills)
        resting = remaining if kind == "LMT" else 0
        if resting:
            self.orders[oid] = {"order_id": oid, "side": side, "price": price,
                                "qty": resting, "seq": event["seq"]}
        assert qty == sum(f["qty"] for f in fills) + resting + (remaining - resting)
        return {"action": action, "filled": qty - remaining,
                "resting": resting, "expired": remaining - resting, "trades": fills}


class Receiver:
    """One global demo sequence. Real feeds usually require channel/session keys."""
    def __init__(self):
        self.books = {s: Book() for s in ASSETS}
        self.expected, self.last_receive = 1, -1.
        self.seen, self.pending, self.applied, self.audit = {}, {}, [], []

    def receive(self, event, received_at):
        times = (event["event_at"], event["published_at"], received_at)
        if any(type(t) not in (int, float) or not math.isfinite(t) for t in times):
            raise ValueError("Times must be finite numbers")
        if received_at < self.last_receive or received_at < event["published_at"]:
            raise ValueError("Arrival precedes previous arrival or publication")
        seq = event["seq"]
        if not positive_int(seq) or event["event_at"] > event["published_at"]:
            raise ValueError("Invalid sequence or event/publication order")
        fingerprint = canonical(event)
        if seq in self.seen:
            if self.seen[seq] != fingerprint:
                raise ValueError("Conflicting payload for an existing sequence")
            self.last_receive = received_at
            self.audit.append({"seq": seq, "received_at": received_at, "status": "DUPLICATE"})
            return
        if seq < self.expected or seq - self.expected > 50:
            raise ValueError("Sequence outside the bounded recovery window")
        self.last_receive = received_at
        self.seen[seq] = fingerprint
        self.pending[seq] = (deepcopy(event), received_at)
        self.audit.append({"seq": seq, "received_at": received_at, "status": "RECEIVED"})
        while self.expected in self.pending:
            item, first_received = self.pending.pop(self.expected)
            symbol = item["symbol"]
            try:
                if symbol not in self.books:
                    raise ValueError("Unknown asset")
                outcome = self.books[symbol].apply(item)
                status, reason = "APPLIED", None
            except ValueError as error:
                outcome, status, reason = {}, "REJECTED", str(error)
            self.applied.append({"seq": self.expected, "symbol": symbol,
                                 "event_at": item["event_at"], "published_at": item["published_at"],
                                 "received_at": first_received, "computed_at": received_at,
                                 "status": status, "reason": reason, **outcome,
                                 "quote": self.books[symbol].quote() if symbol in self.books else None})
            self.expected += 1

    def snapshot(self):
        # Any pending event implies a gap in this single global feed.
        gap = bool(self.pending)
        return {"as_of_receive": self.last_receive, "last_contiguous_seq": self.expected - 1,
                "feed_status": "GAP" if gap else "CONTIGUOUS",
                "quotes": None if gap else {s: b.quote() for s, b in self.books.items()}}


def call_auction(buys, sells, reference):
    """Toy rule: max volume, min imbalance, nearest reference, then lower tick."""
    if not positive_int(reference) or any(not positive_int(p) or not positive_int(q)
                                          for p, q in buys + sells):
        raise ValueError("Auction prices and quantities must be positive integers")
    candidates = sorted({reference} | {p for p, _ in buys + sells})
    rows = []
    for p in candidates:
        demand = sum(q for price, q in buys if price >= p)
        supply = sum(q for price, q in sells if price <= p)
        rows.append({"price": p, "demand": demand, "supply": supply,
                     "volume": min(demand, supply), "imbalance": abs(demand - supply)})
    best = min(rows, key=lambda r: (-r["volume"], r["imbalance"], abs(r["price"] - reference), r["price"]))
    return {"rule": "DEMO_CALL_V1", "price": best["price"] if best["volume"] else None,
            "volume": best["volume"], "candidates": rows}


def demo_events():
    events = []
    def add(symbol, action, oid, qty, side=None, price=None, kind="LMT"):
        seq = len(events) + 1
        events.append({"source": "SYNTHETIC", "symbol": symbol, "seq": seq,
                       "event_at": float(seq), "published_at": seq + .01,
                       "action": action, "order_id": oid, "qty": qty,
                       "side": side, "price": price, "kind": kind})
    add("EQ_DEMO", "NEW", "B1", 80, "B", 9998)
    add("EQ_DEMO", "NEW", "A1", 30, "S", 10002)
    add("EQ_DEMO", "NEW", "A2", 20, "S", 10002)
    add("EQ_DEMO", "NEW", "A3", 100, "S", 10004)
    add("EQ_DEMO", "NEW", "M1", 120, "B", kind="MKT")
    add("EQ_DEMO", "CANCEL", "A3", 30)
    add("EQ_DEMO", "NEW", "A4", 200, "S", 10010)
    add("EQ_DEMO", "NEW", "B2", 100, "B", 10000)
    add("EQ_DEMO", "NEW", "BAD", -5, "S", 10012)
    for symbol, bid, ask in [("BOND_DEMO", 9999, 10001),
                              ("GOLD_DEMO", 19995, 20005), ("FX_DEMO", 69999, 70001)]:
        add(symbol, "NEW", symbol + "B", 100, "B", bid)
        add(symbol, "NEW", symbol + "S", 100, "S", ask)
    return events


def main():
    events = demo_events()
    receiver, snapshots, arrivals = Receiver(), [], []
    # Sequence 4 arrives before 3; the first copy of 3 arrives at 4.2.
    schedule = [(1, 1.1), (2, 2.1), (4, 4.1), (3, 4.2), (3, 4.3)]
    schedule += [(i, i + .1) for i in range(5, len(events) + 1)]
    for seq, arrival in schedule:
        event = events[seq - 1]
        arrivals.append({"received_at": arrival, "event": event})
        receiver.receive(event, arrival)
        snapshots.append(receiver.snapshot())
    fills = receiver.books["EQ_DEMO"].trades
    total = sum(f["qty"] for f in fills)
    vwap = sum(f["price"] * f["qty"] for f in fills) / total
    summary = {"source": "SYNTHETIC", "events": len(events), "arrivals": len(arrivals),
               "applied": sum(r["status"] == "APPLIED" for r in receiver.applied),
               "rejected": sum(r["status"] == "REJECTED" for r in receiver.applied),
               "duplicates": sum(r["status"] == "DUPLICATE" for r in receiver.audit),
               "fills": fills, "vwap_ticks": vwap, "buy_cost_bps": (vwap / 10000 - 1) * 10000,
               "auction": call_auction([(10002, 80), (10000, 70)],
                                        [(9998, 60), (10000, 90)], 10000),
               "final_snapshot": receiver.snapshot()}
    out = Path(__file__).parent / "runs" / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True, exist_ok=False)
    for name, rows in [("arrivals", arrivals), ("applied", receiver.applied),
                       ("audit", receiver.audit), ("snapshots", snapshots)]:
        (out / (name + ".jsonl")).write_text("".join(canonical(r) + "\n" for r in rows), encoding="utf-8")
    manifest = {"python": platform.python_version(), "rules": "DEMO_CONTINUOUS_V1",
                "price_unit": "integer tick; EQ_DEMO tick=0.01 CNY, other assets illustrative",
                "summary": summary, "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in [Path(__file__), *sorted(out.glob("*.jsonl"))]}}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2,
                                                 allow_nan=False), encoding="utf-8")
    print(out.resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
