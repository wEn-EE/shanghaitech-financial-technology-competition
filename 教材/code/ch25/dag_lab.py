"""Run chapters 23 and 24 as recoverable, separately cached SQLite stages."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
import uuid

import numpy as np

from lineage_lab import canonical, connect, digest, put, read
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ch23"), str(ROOT / "ch24")]
import fusion_lab
import nested_lab
import lineage_lab


def startup(db, *, recover=False):
    # Run only with exclusive operational ownership of this teaching database.
    db.execute("""CREATE TABLE IF NOT EXISTS requests(
       id TEXT PRIMARY KEY, parent_request TEXT REFERENCES requests(id),
       stage TEXT NOT NULL, stage_run TEXT NOT NULL REFERENCES runs(id))""")
    db.execute("""CREATE TABLE IF NOT EXISTS run_inputs(
       consumer TEXT NOT NULL REFERENCES runs(id), role TEXT NOT NULL,
       artifact TEXT NOT NULL REFERENCES artifacts(hash), producer TEXT REFERENCES runs(id),
       PRIMARY KEY(consumer,role))""")
    db.commit()
    if recover:
        with db:
            db.execute("UPDATE runs SET status='FAILED',error='INTERRUPTED' WHERE status='RUNNING'")


def stage(db, name, parents, params, implementation, action, stop=False, *, upstream=None):
    upstream = dict(upstream or {})
    for role, producer in upstream.items():
        match = db.execute("""SELECT manifest_hash FROM runs
            WHERE id=? AND status='SUCCESS'""", (producer,)).fetchone()
        if not match or json.loads(read(db, match[0]))["output"] != parents[role]:
            raise ValueError("upstream run does not supply the declared input")
    signatures = [digest(Path(path).read_bytes()) for path in (__file__, implementation, lineage_lab.__file__)]
    recipe = {"stage": name, "inputs": parents, "params": params, "code": signatures,
              "python": platform.python_version(), "numpy": np.__version__, "sqlite": sqlite3.sqlite_version}
    recipe["upstream_runs"] = upstream
    body = canonical(recipe)
    key = digest(body)
    found = db.execute("SELECT id,manifest_hash FROM runs WHERE recipe_hash=? AND status='SUCCESS'",
                       (key,)).fetchone()
    inputs = {role: json.loads(read(db, value)) for role, value in parents.items()}
    if found:
        manifest = json.loads(read(db, found[1]))
        if manifest["recipe"] != key:
            raise ValueError("cached recipe mismatch")
        read(db, manifest["recipe"])
        read(db, manifest["output"])
        return {"run": found[0], "output": manifest["output"], "cached": True}

    attempt = str(uuid.uuid4())
    with db:
        put(db, body)
        db.execute("INSERT INTO runs VALUES (?,?,?,NULL,NULL)", (attempt, key, "RUNNING"))
    try:
        output = canonical(action(inputs, params))
        with db:
            result = put(db, output)
            manifest = put(db, canonical({"recipe": key, "output": result}))
            db.executemany("INSERT INTO run_inputs VALUES (?,?,?,?)",
                           [(attempt, role, artifact, upstream.get(role))
                            for role, artifact in parents.items()])
            for role, parent in {"recipe": key, **parents}.items():
                db.execute("INSERT INTO edges VALUES (?,?,?,?)", (attempt, parent, result, role))
            if stop:
                os._exit(73)  # Invoked only by the disposable child process.
            db.execute("UPDATE runs SET status='SUCCESS',manifest_hash=? WHERE id=?",
                       (manifest, attempt))
        return {"run": attempt, "output": result, "cached": False}
    except Exception as exc:
        with db:
            db.execute("UPDATE runs SET status='FAILED',error=? WHERE id=?",
                       (type(exc).__name__, attempt))
        raise


def run(db, raw, folds, parent=None, stop=False):
    with db:
        raw_id = put(db, canonical(raw))
        quote_id = put(db, canonical(raw["quotes"]))
    feature = stage(db, "fusion", {"raw": raw_id}, {}, fusion_lab.__file__,
                    lambda v,p: fusion_lab.build(v["raw"]["documents"],
                                                 v["raw"]["quotes"], v["raw"]["annotations"]))
    coverage = stage(db, "quote_coverage", {"quotes": quote_id}, {}, __file__,
                     lambda v,p: {"quotes": len(v["quotes"]),
                                  "delayed": sum(q["ready"] > q["time"] for q in v["quotes"])})
    def evaluate(v, p):
        return nested_lab.evaluate(v["fusion"], starts=p["folds"])
    validation = stage(db, "validation", {"fusion": feature["output"]},
                       {"folds": folds}, nested_lab.__file__, evaluate, stop,
                       upstream={"fusion": feature["run"]})
    request = str(uuid.uuid4())
    stages = {"fusion": feature, "quote_coverage": coverage, "validation": validation}
    with db:
        for name, value in stages.items():
            db.execute("INSERT INTO requests VALUES (?,?,?,?)",
                       (f"{request}:{name}", parent, name, value["run"]))
    return stages, f"{request}:validation"


def ancestors(db, key):
    sql = """WITH RECURSIVE lineage(hash) AS (
       SELECT ? UNION
       SELECT e.parent FROM lineage l JOIN edges e ON e.child=l.hash
       JOIN runs r ON r.id=e.run_id WHERE r.status='SUCCESS')
       SELECT hash FROM lineage ORDER BY hash"""
    return [r[0] for r in db.execute(sql, (key,))]


def trace_run(db, run_id):
    row = db.execute("SELECT recipe_hash FROM runs WHERE id=? AND status='SUCCESS'",
                     (run_id,)).fetchone()
    if row is None:
        raise ValueError("unknown successful run")
    recipe = json.loads(read(db, row[0]))
    if "upstream_runs" not in recipe:
        return {"run": run_id, "lineage": "UNKNOWN_LEGACY"}
    inputs = {}
    for role, artifact, producer in db.execute(
            "SELECT role,artifact,producer FROM run_inputs WHERE consumer=? ORDER BY role", (run_id,)):
        inputs[role] = {"artifact": artifact, "producer": trace_run(db, producer) if producer else None}
    return {"run": run_id, "inputs": inputs}


def load_raw(path):
    supplied = json.loads(path.read_bytes())
    return supplied.get("raw", supplied)


def main():
    import subprocess
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fusion", type=Path, help="chapter 23 fusion.json containing raw inputs")
    parser.add_argument("--crash-child", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    raw = load_raw(args.fusion)
    if args.crash_child:
        with closing(connect(args.crash_child)) as db:
            startup(db)
            run(db, raw, [48,64], stop=True)
        return
    out = Path(__file__).parent / "runs" / datetime.now(timezone.utc).strftime("dag_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True)
    path = out / "dag.sqlite"
    with closing(connect(path)) as db:
        startup(db)
        first, request = run(db, raw, [48,64,80])
    failed = subprocess.run([sys.executable, "-X", "utf8", __file__, str(args.fusion),
                             "--crash-child", str(path)], check=False)
    if failed.returncode != 73:
        raise RuntimeError("child did not stop at requested transaction boundary")
    with closing(connect(path)) as db:
        assert db.execute("SELECT COUNT(*) FROM runs WHERE status='RUNNING'").fetchone()[0] == 1
        incident = db.execute("SELECT id,manifest_hash FROM runs WHERE status='RUNNING'").fetchone()
        assert incident[1] is None
        assert db.execute("SELECT COUNT(*) FROM edges WHERE run_id=?", (incident[0],)).fetchone()[0] == 0
        startup(db, recover=True)
        retry, retry_request = run(db, raw, [48,64], parent=request)
        assert db.execute("SELECT parent_request FROM requests WHERE id=?",
                          (retry_request,)).fetchone()[0] == request
        hit, _ = run(db, raw, [48,64], parent=request)
        assert all(hit[name]["cached"] for name in hit)
        assert retry["fusion"]["cached"] and retry["quote_coverage"]["cached"] and not retry["validation"]["cached"]
        validation_id = retry["validation"]["output"]
        links = ancestors(db, validation_id)
        decision_trace = trace_run(db, retry["validation"]["run"])
        assert decision_trace["inputs"]["fusion"]["producer"]["run"] == first["fusion"]["run"]
        assert digest(canonical(raw)) in links
        assert first["validation"]["output"] != validation_id
        assert json.loads(read(db, first["validation"]["output"]))["folds"][:2] == json.loads(read(db, validation_id))["folds"]
        changed_raw = dict(raw, documents=[dict(d) for d in raw["documents"]])
        changed_raw["documents"][-1]["text"] = "修订实验：无可识别实体。"
        changed, _ = run(db, changed_raw, [48,64], parent=request)
        assert changed["quote_coverage"]["cached"]
        assert not changed["fusion"]["cached"] and not changed["validation"]["cached"]
        info = {"decision_trace": decision_trace, "news_edit": changed, "first": first, "recovered": retry, "repeated": hit, "ancestors": links, "initial_request": request, "recovered_request": retry_request,
                "interrupted": db.execute("SELECT COUNT(*) FROM runs WHERE error='INTERRUPTED'").fetchone()[0],
                "integrity": db.execute("PRAGMA integrity_check").fetchone()[0]}
    (out / "report.json").write_bytes(canonical(info))
    print(out)
    print({key: {k: v["cached"] for k,v in info[key].items()} for key in ("first","recovered","repeated","news_edit")})
    print("Ancestors:", len(links), "Interrupted:", info["interrupted"], "Integrity:", info["integrity"])


if __name__ == "__main__":
    main()
