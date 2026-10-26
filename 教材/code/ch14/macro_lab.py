"""SYNTHETIC macro releases: immutable vintages and point-in-time snapshots."""
from __future__ import annotations

import calendar
import hashlib
import json
import math
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import stdev

UTC = timezone.utc
SERIES = ("GROWTH_DEMO", "INFLATION_DEMO")
THRESHOLDS = {"GROWTH_DEMO": 4.0, "INFLATION_DEMO": 2.0}


@dataclass(frozen=True)
class Release:
    event_id: str
    series: str
    period_end: datetime
    version: int
    published_at: datetime
    available_at: datetime
    value: float
    unit: str = "percent_yoy"


@dataclass(frozen=True)
class Forecast:
    forecast_id: str
    series: str
    period_end: datetime
    available_at: datetime
    value: float
    unit: str = "percent_yoy"


class Ledger:
    def __init__(self):
        self.events: dict[str, Release] = {}
        self.audit: list[dict] = []

    def add(self, e: Release) -> bool:
        times = (e.period_end, e.published_at, e.available_at)
        reason = None
        if any(t.tzinfo is None or t.utcoffset() is None for t in times):
            reason = "NAIVE_TIME"
        elif not e.period_end <= e.published_at <= e.available_at:
            reason = "TIME_ORDER"
        elif e.series not in SERIES or e.unit != "percent_yoy":
            reason = "SCHEMA"
        elif e.version < 1 or not math.isfinite(e.value):
            reason = "VALUE_OR_VERSION"
        old = self.events.get(e.event_id)
        if not reason and old is not None:
            reason = "DUPLICATE" if old == e else "ID_CONFLICT"
        if not reason:
            for prior in self.events.values():
                if (prior.series, prior.period_end) != (e.series, e.period_end):
                    continue
                if prior.version == e.version:
                    reason = "VERSION_CONFLICT"
                elif ((e.version > prior.version) !=
                      (e.published_at > prior.published_at)) or (
                        e.published_at == prior.published_at):
                    reason = "VERSION_ORDER"
        self.audit.append({"event_id": e.event_id, "action": reason or "ACCEPT"})
        if reason == "DUPLICATE":
            return False
        if reason:
            raise ValueError(reason)
        self.events[e.event_id] = e
        return True

    def snapshot(self, series, decision_at, max_age_days=60):
        candidates = [e for e in self.events.values()
                      if e.series == series and e.available_at <= decision_at]
        if not candidates:
            return None, "MISSING"
        # Arrival order must not overwrite a newer period or a newer vintage.
        chosen = max(candidates, key=lambda e: (e.period_end, e.version))
        age = (decision_at - chosen.period_end).total_seconds() / 86400
        return chosen, "STALE" if age > max_age_days else "OK"


def forecast_before(e, forecasts):
    rows = [f for f in forecasts if f.series == e.series
            and f.period_end == e.period_end and f.unit == e.unit
            and f.available_at < e.published_at and math.isfinite(f.value)]
    return max(rows, key=lambda f: (f.available_at, f.forecast_id)) if rows else None


def surprise(e, ledger, forecasts, min_history=6):
    if e.version != 1:
        raise ValueError("REVISIONS_ARE_NOT_FIRST_RELEASE_SURPRISES")
    f = forecast_before(e, forecasts)
    if f is None:
        return {"event_id": e.event_id, "reason": "NO_PRE_RELEASE_FORECAST",
                "raw_pp": None, "z": None, "history_n": 0}
    history = []
    for h in ledger.events.values():
        if (h.series == e.series and h.version == 1
                and h.published_at < e.published_at
                and h.available_at < e.published_at):
            hf = forecast_before(h, forecasts)
            if hf is not None:
                history.append(h.value - hf.value)
    raw = e.value - f.value
    scale = stdev(history) if len(history) >= min_history else None
    reason = "OK" if scale is not None and scale > 1e-12 else "WARMUP_OR_ZERO_SCALE"
    return {"event_id": e.event_id, "forecast_id": f.forecast_id,
            "raw_pp": raw, "scale_pp": scale,
            "z": raw / scale if reason == "OK" else None,
            "history_n": len(history), "reason": reason}


def quadrant(values):
    return "/".join(("G_HIGH" if values[0] >= 4 else "G_LOW",
                     "I_HIGH" if values[1] >= 2 else "I_LOW"))


def dataset():
    events, forecasts, decisions = [], [], []
    for k in range(36):
        year, month0 = 2022 + k // 12, k % 12
        end = datetime(year, month0 + 1,
                       calendar.monthrange(year, month0 + 1)[1], tzinfo=UTC)
        decisions.append(end + timedelta(days=18, hours=12))
        for j, series in enumerate(SERIES):
            center = THRESHOLDS[series] + (0.65 if j == 0 else 0.45) * math.sin(k / 3 + j)
            error = 0.32 * math.cos(1.7 * k + j)
            first = center + error
            revised = first + 0.48 * math.sin(0.9 * k + j)
            pub = end + timedelta(days=15 if j == 0 else 10, hours=8)
            delay = timedelta(days=6) if k == 10 and j == 0 else timedelta(minutes=5)
            tag = f"{series}:{k:02d}"
            events.extend([
                Release(tag + ":1", series, end, 1, pub, pub + delay, first),
                Release(tag + ":2", series, end, 2, pub + timedelta(days=90),
                        pub + timedelta(days=90, minutes=5), revised)])
            # One forecast arrives after publication: unusable as an expectation.
            ftime = pub + timedelta(minutes=1) if k == 12 and j == 1 else pub - timedelta(days=1)
            forecasts.append(Forecast(tag + ":F", series, end, ftime, center))
    return sorted(events, key=lambda e: (e.available_at, e.event_id)), forecasts, decisions


def experiment(events, forecasts, decisions):
    ledger = Ledger()
    for e in events:
        ledger.add(e)
    ledger.add(events[0])  # Deliberate retry: retained in the audit log.
    rows = []
    for t in decisions:
        selected = [ledger.snapshot(s, t) for s in SERIES]
        valid = all(e is not None and status == "OK" for e, status in selected)
        pit = quadrant([e.value for e, _ in selected]) if valid else "UNKNOWN"
        # Invalid counterfactual: future revision, but keep the SAME selected periods.
        final = [max((x for x in events if x.series == e.series and
                      x.period_end == e.period_end), key=lambda x: x.version)
                 for e, _ in selected if e is not None]
        leaky = quadrant([e.value for e in final]) if valid else "UNKNOWN"
        rows.append({"decision_at": t, "pit_state": pit,
                     "LEAKY_DIAGNOSTIC_state": leaky,
                     "selected": [{"event": asdict(e) if e else None, "status": s}
                                  for e, s in selected]})
    surprises = [surprise(e, ledger, forecasts) for e in events if e.version == 1]
    revisions = []
    for e in events:
        if e.version == 2:
            original = next(x for x in events if x.series == e.series
                            and x.period_end == e.period_end and x.version == 1)
            revisions.append({"event_id": e.event_id, "available_at": e.available_at,
                              "revision_pp": e.value - original.value})
    results = {"data_kind": "SYNTHETIC", "events": len(events),
               "snapshots": len(rows),
               "revision_state_disagreements": sum(r["pit_state"] != r["LEAKY_DIAGNOSTIC_state"] for r in rows),
               "standardized_surprises": sum(s["z"] is not None for s in surprises),
               "missing_pre_release_forecasts": sum(s["reason"] == "NO_PRE_RELEASE_FORECAST" for s in surprises),
               "duplicates": sum(a["action"] == "DUPLICATE" for a in ledger.audit)}
    return results, rows, surprises, revisions, ledger.audit


def encode(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def main():
    events, forecasts, decisions = dataset()
    results, rows, surprises, revisions, audit = experiment(events, forecasts, decisions)
    out = Path(__file__).parent / "runs" / datetime.now(UTC).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True, exist_ok=False)
    artifacts = {"inputs.json": {"releases": [asdict(e) for e in events],
                                 "forecasts": [asdict(f) for f in forecasts],
                                 "decisions": decisions},
                 "results.json": results, "snapshots.json": rows,
                 "surprises.json": surprises, "revisions.json": revisions,
                 "audit.json": audit}
    hashes = {}
    for name, data in artifacts.items():
        path = out / name
        path.write_text(json.dumps(data, default=encode, ensure_ascii=False,
                                   indent=2, allow_nan=False) + "\n", encoding="utf-8")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"python": platform.python_version(), "data_kind": "SYNTHETIC",
                "thresholds_percent": THRESHOLDS, "min_history": 6,
                "freshness_basis": "period_end", "max_age_days": 60,
                "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "files_sha256": hashes,
                "limitations": "Offline replay; no real calendar, forecasts, causal estimate or trading."}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(out.resolve())


if __name__ == "__main__":
    main()
