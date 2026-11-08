"""Synthetic PIT ledger. Standard library only; no live market connection."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import platform
import sqlite3

BASE = "2026-11-02T00:00:00+00:00"
SCHEMA = """
CREATE TABLE vintage (
    id TEXT PRIMARY KEY,
    series TEXT NOT NULL,
    period TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision > 0),
    value INTEGER,
    status TEXT NOT NULL CHECK(status IN ('OK','WITHDRAWN')),
    published INTEGER NOT NULL,
    received INTEGER NOT NULL,
    ready INTEGER NOT NULL,
    UNIQUE(series, period, revision),
    CHECK(published >= 0 AND published <= received AND received <= ready),
    CHECK((status='OK' AND value IS NOT NULL) OR
          (status='WITHDRAWN' AND value IS NULL))
) STRICT;
CREATE INDEX visible_idx ON vintage(series, ready, period, revision);
CREATE TRIGGER no_update BEFORE UPDATE ON vintage
BEGIN SELECT RAISE(ABORT, 'append only'); END;
CREATE TRIGGER no_delete BEFORE DELETE ON vintage
BEGIN SELECT RAISE(ABORT, 'append only'); END;
"""
PIT_SQL = """
WITH visible AS (
    SELECT * FROM vintage WHERE series=? AND ready<=?
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY series, period ORDER BY revision DESC
    ) AS rn FROM visible
)
SELECT id, series, period, revision, value, status, published, received, ready
FROM ranked WHERE rn=1 ORDER BY period
"""


@dataclass(frozen=True)
class Vintage:
    id: str
    series: str
    period: str
    revision: int
    value: int | None
    status: str
    published: int
    received: int
    ready: int


def new_db(path=":memory:"):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def append(db, v):
    """Input is an already validated first-acceptance record, not a delivery."""
    parsed = datetime.strptime(v.period, "%Y-%m")
    if parsed.strftime("%Y-%m") != v.period:
        raise ValueError("period must be canonical YYYY-MM")
    for name in ("revision", "published", "received", "ready"):
        if type(getattr(v, name)) is not int:
            raise ValueError("integer required: " + name)
    if v.value is not None and type(v.value) is not int:
        raise ValueError("value must be integer or None")
    old = db.execute(
        "SELECT * FROM vintage WHERE series=? AND period=? AND revision=?",
        (v.series, v.period, v.revision)
    ).fetchone()
    if old is not None:
        if dict(old) == asdict(v):
            return "DUPLICATE"
        raise ValueError("conflicting normalized version")
    with db:
        db.execute("INSERT INTO vintage VALUES (?,?,?,?,?,?,?,?,?)",
                   tuple(asdict(v).values()))
    return "ACCEPTED"


def asof(db, cutoff, series="CPI_DEMO"):
    if type(cutoff) is not int or cutoff < 0:
        raise ValueError("cutoff must be nonnegative integer seconds")
    return [dict(r) for r in db.execute(PIT_SQL, (series, cutoff))]


def period_at(db, cutoff, period):
    return next((r for r in asof(db, cutoff) if r["period"] == period), None)


def current_at(db, cutoff):
    rows = asof(db, cutoff)
    # A withdrawn newest period remains withdrawn; do not resurrect older data.
    return rows[-1] if rows else None


def freeze_feature(db, cutoff, completed):
    if type(completed) is not int or completed < cutoff:
        raise ValueError("completion precedes snapshot")
    row = current_at(db, cutoff)
    return {"cutoff": cutoff, "completed": completed, "input": row,
            "feature_code": "latest-period-v1"}


def infer(feature, rule, decision):
    if type(decision) is not int:
        raise ValueError("decision must be integer")
    if decision < max(feature["completed"], rule["ready"]):
        raise ValueError("feature or rule not yet available")
    row = feature["input"]
    label = "UNKNOWN"
    if row is not None and row["status"] == "OK":
        label = "HIGH" if row["value"] >= rule["threshold"] else "LOW"
    return {"decision": decision, "label": label, "rule": dict(rule),
            "feature": feature}


def samples():
    return [
        Vintage("sep-v1", "CPI_DEMO", "2026-09", 1, 230, "OK", 10, 12, 15),
        Vintage("oct-v1", "CPI_DEMO", "2026-10", 1, 240, "OK", 40, 42, 50),
        Vintage("sep-v2", "CPI_DEMO", "2026-09", 2, 270, "OK", 60, 65, 80),
        Vintage("oct-v2", "CPI_DEMO", "2026-10", 2, None, "WITHDRAWN",
                100, 105, 110),
        Vintage("oct-v3", "CPI_DEMO", "2026-10", 3, 260, "OK", 120, 125, 130),
    ]


def run(db):
    events = samples()
    for v in events:
        append(db, v)
    cuts = [12, 15, 50, 70, 80, 110, 130]
    views = {str(c): asof(db, c) for c in cuts}
    # Deliberately WRONG: rank all versions, then filter readiness.
    wrong = db.execute("""
        WITH ranked AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY series, period ORDER BY revision DESC
          ) AS rn FROM vintage
        )
        SELECT id FROM ranked WHERE rn=1 AND ready<=20
    """).fetchall()
    rule = {"id": "rule-v2", "ready": 90, "threshold": 250}
    frozen = freeze_feature(db, 70, 75)
    try:
        infer(frozen, rule, 80)
    except ValueError as exc:
        rejected = str(exc)
    else:
        raise AssertionError("future rule was accepted")
    return {
        "data_kind": "SYNTHETIC", "base_utc": BASE,
        "unit": "percent scaled by 100", "inputs": [asdict(v) for v in events],
        "snapshots": views, "wrong_rank_first_at_20": [r["id"] for r in wrong],
        "rejected_at_80": rejected,
        "prediction_at_90": infer(frozen, rule, 90),
        "prediction_at_135": infer(freeze_feature(db, 130, 132), rule, 135),
        "september_comparison": [
            {"cutoff": c, "pit": period_at(db, c, "2026-09")["value"],
             "restated": period_at(db, 130, "2026-09")["value"]}
            for c in (20, 70)
        ]
    }


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = Path(__file__).parent / "runs" / ("run_" + stamp)
    out.mkdir(parents=True)
    db = new_db(out / "pit.db")
    try:
        result = run(db)
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        db.close()
    target = out / "results.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    manifest = {
        "data_kind": "SYNTHETIC", "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version, "integrity_check": integrity,
        "program_sha256": digest(Path(__file__)),
        "results_sha256": digest(target), "db_sha256": digest(out / "pit.db"),
        "policy": "ready<=cutoff; revision per period; then newest period"
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"run_dir": str(out), **manifest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
