"""Single fixed leader, committed log, deterministic teaching clock (milliseconds)."""
import argparse
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    version: int
    price_atoms: int
    event_ms: int


class Cluster:
    def __init__(self, initial):
        self.log = [Entry(1, initial, 0)]
        self.applied = {node: 1 for node in "ABC"}
        self.reachable = set("ABC")
        self.history = []

    def write(self, price_atoms, now):
        # A synchronous abstract step: A and one reachable peer install v.
        peers = sorted(self.reachable - {"A"})
        if not peers:
            self.history.append(dict(at=now, op="write", result="NO_QUORUM"))
            return False
        version = len(self.log) + 1
        self.log.append(Entry(version, price_atoms, now))
        for node in ("A", peers[0]):
            self.applied[node] = version
        self.history.append(dict(at=now, op="write", peer=peers[0],
                                 result="COMMITTED", version=version, price_atoms=price_atoms))
        return True

    def deliver(self, node, version):
        if node not in self.reachable:
            return "DISCONNECTED"
        if version <= self.applied[node]:
            return "REPLAY"
        if version != self.applied[node] + 1 or version > len(self.log):
            return "GAP"
        self.applied[node] = version
        return "APPLIED"

    def read(self, node, policy, now, min_version=1, max_age=20):
        if policy not in ("local", "strict", "guarded"):
            raise ValueError("unknown policy")
        # All inter-node RPCs go through A. Local reads consult only the prefix.
        result = {"at": now, "op": "read", "node": node, "policy": policy}
        if policy == "strict" and node not in self.reachable:
            result["status"] = "UNAVAILABLE"
        else:
            target = "A" if policy == "strict" else node
            entry = self.log[self.applied[target] - 1]
            age = now - entry.event_ms
            if age < 0:
                raise ValueError("clock precedes event")
            result.update(version=entry.version, event_ms=entry.event_ms, age_ms=age)
            if policy == "guarded" and entry.version < min_version:
                result["status"] = "BEHIND_SESSION"
            elif policy == "guarded" and age > max_age:
                result["status"] = "EXPIRED"
            else:
                result.update(status="OK", price_atoms=entry.price_atoms)
        self.history.append(result)
        return result


def seed_price(dbpath):
    with closing(sqlite3.connect(dbpath.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        rows = db.execute("""SELECT q.price_atoms, i.price_scale, e.event_uid
            FROM quote q JOIN instrument i USING(instrument_id)
            JOIN event e USING(event_uid)
            WHERE q.instrument_id='EQ_DEMO' AND e.source_id='DEMO'""").fetchall()
    if len(rows) != 1 or rows[0][1] != 2:
        raise ValueError("expected the chapter 26 single equity quote at scale 2")
    return rows[0][0], rows[0][2]


def experiment(initial):
    c = Cluster(initial)
    c.read("C", "local", 5)
    c.reachable.remove("C")
    c.write(initial - 300, 10)
    c.read("B", "strict", 11)
    c.read("C", "local", 12)
    c.read("C", "strict", 13)
    c.read("C", "guarded", 14, min_version=2)
    c.read("C", "guarded", 25)
    c.write(initial - 400, 30)
    c.reachable.add("C")
    delivery = []
    for time, version in ((31, 3), (32, 2), (33, 2), (34, 3)):
        delivery.append(dict(at=time, version=version, status=c.deliver("C", version)))
    c.read("C", "guarded", 35, min_version=3)
    c.reachable = {"A"}
    c.write(initial + 1, 40)
    return dict(data="SYNTHETIC", clock_unit="ms", log=[asdict(e) for e in c.log],
                operations=c.history, delivery=delivery, final_prefix=c.applied)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    price, uid = seed_price(args.ledger)
    print(json.dumps(dict(source_event_uid=uid, **experiment(price)), indent=2))
