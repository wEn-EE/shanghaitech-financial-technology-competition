"""Replay chapter 33 report obligations under a deterministic two-slot scheduler."""
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ch33"))
from recovery_lab import source_rows


@dataclass(frozen=True)
class Task:
    name: str
    release: int
    seconds: int
    parents: tuple
    kind: str
    report: int = -1


def workload(rows, quantum):
    tasks = []
    prior = {}
    for i, window, _, t, _, _ in rows:
        check, put = f"check{i}", f"put{i}"
        tasks.append(Task(check, t - 184, 2, (), "check", i))
        deps = (check,) + prior.get(window, ())
        tasks.append(Task(put, t - 184, 1, deps, "put", i))
        prior[window] = (put,)
    for batch in ("X", "Y"):
        deps = ()
        for start in range(0, 12, quantum):
            name = f"{batch}-{start:02}"
            tasks.append(Task(name, 0, min(quantum, 12 - start), deps, "batch"))
            deps = (name,)
    return tasks


def simulate(rows, quantum=12, batch_limit=2):
    pending = {task.name: task for task in workload(rows, quantum)}
    running, done, visible, starts = {}, {}, {}, []
    now = 0
    lost_ack = True
    while pending or running:
        for name, (end, task) in list(running.items()):
            if end != now:
                continue
            del running[name]
            if task.kind == "put":
                row = rows[task.report]
                key = row[1:3]
                payload = row[3:]
                if key in visible and visible[key][1] != payload:
                    raise ValueError("inconsistent publication")
                visible.setdefault(key, (now, payload))
                if task.report == 1 and lost_ack:
                    lost_ack = False
                    pending[name] = Task(name, now + 2, 1, task.parents, "put", 1)
                    continue
            done[name] = now
        ready = [task for task in pending.values()
                 if task.release <= now and all(p in done for p in task.parents)]
        for task in sorted(ready, key=lambda x: (x.kind == "batch", x.name)):
            if len(running) == 2:
                break
            n_batch = sum(job.kind == "batch" for _, job in running.values())
            if task.kind == "batch" and n_batch >= batch_limit:
                continue
            starts.append((now, task.name))
            running[task.name] = now + task.seconds, task
            del pending[task.name]
        future = [end for end, _ in running.values()]
        future.extend(t.release for t in pending.values() if t.release > now)
        if not future and pending:
            raise ValueError("unschedulable tasks")
        if future:
            now = min(future)
    assert {k: v[1] for k, v in visible.items()} == {r[1:3]: r[3:] for r in rows}
    delays = [visible[r[1:3]][0] - (r[3] - 184) for r in rows]
    last_batch = max(t for name, t in done.items() if name.startswith(("X-", "Y-")))
    return delays, last_batch, starts, done


def placements(capacity):
    rates = (600, 400, 350, 250, 200, 100)
    sizes = (900, 80, 60, 250, 50, 100)
    old = (0, 0, 0, 1, 1, 1)
    feasible = []
    for owners in product(range(3), repeat=len(rates)):
        loads = tuple(sum(r for r, w in zip(rates, owners) if w == j)
                      for j in range(3))
        if max(loads) <= capacity:
            moved = sum(s for s, a, b in zip(sizes, old, owners) if a != b)
            feasible.append((moved, max(loads), owners, loads))
    return min(feasible) if feasible else None


if __name__ == "__main__":
    rows = source_rows(Path(sys.argv[1]))
    for label, q, limit in [("shared", 12, 2), ("reserved", 12, 1), ("sliced", 3, 2)]:
        delays, batch_end, starts, done = simulate(rows, q, limit)
        print(label, delays, batch_end, [t for t, name in starts if name == "put1"])
    for cap in (800, 650, 620):
        print(cap, placements(cap))
